# modules/validar_formulacion_detalle.py
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List
from config.db import get_connections, get_store_connection
from decimal import Decimal, ROUND_HALF_UP

def _chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def _col_idx_to_excel(col_idx: int) -> str:
    """Convierte índice 0-based a letra(s) Excel (0 -> A, 26 -> AA)."""
    col = ""
    n = col_idx + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        col = chr(65 + rem) + col
    return col

def limpiar_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas clave para evitar falsos positivos."""
    if df.empty:
        return df
    for c in ["idformulacion", "id_Insumo", "Formula", "Insumo", "Unidad"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    if "Almacen" in df.columns:
        df["Almacen"] = df["Almacen"].astype(str).str.strip()
    if "Cantidad" in df.columns:
        df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce")
    return df

def validar_formulacion_detalle_varias(
    tiendas: List[int],
    nombre_archivo: str = None
) -> str:
    carpeta = Path("SincroSIG/logs/formulaciones")
    carpeta.mkdir(parents=True, exist_ok=True)

    if not nombre_archivo:
        fecha = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nombre_archivo = f"validacion_formulacion_detalle_{fecha}.xlsx"

    ruta = carpeta / nombre_archivo

    q_formu_tda = """
        SELECT f.idformulacion
        FROM formulacion f
        INNER JOIN formulaciondet fd ON fd.idformulacion = f.idformulacion
        LEFT JOIN preciart p ON p.idarticulos = f.idarticulos
        WHERE f.idtienda = {id_tienda}
          AND f.activo = 1
          AND p.estado = 1
        GROUP BY f.idformulacion
    """

    q_detalle_template = """
        SELECT DISTINCT
          f.idformulacion,
          f.descripcion AS Formula,
          fd.idarticulos AS id_Insumo,
          a.descrip1 AS Insumo,
          fd.cantidad AS Cantidad,
          u.descrip AS Unidad,
          fd.idalmacen AS Almacen
        FROM formulaciondet fd
        INNER JOIN formulacion f ON f.idformulacion = fd.idformulacion
        LEFT JOIN preciart p ON p.idarticulos = f.idarticulos
        INNER JOIN articulos a ON a.idarticulos = fd.idarticulos
        INNER JOIN unidadmed u ON u.idunidadmed = fd.idunidadmed
        WHERE f.idformulacion IN ({ids})
          AND f.activo = 1
          AND p.estado = 1
    """

    with pd.ExcelWriter(ruta, engine="xlsxwriter") as writer:
        for id_tienda in tiendas:
            conn_sig, cur_sig, _, _ = get_connections()
            conn_tda, cur_tda = get_store_connection(id_tienda)
            try:
                # 1) IDs de formulaciones en la tienda
                cur_tda.execute(q_formu_tda.format(id_tienda=id_tienda))
                filas = cur_tda.fetchall()
                if not filas:
                    pd.DataFrame([{"Mensaje": "Sin formulaciones activas en la tienda"}]).to_excel(
                        writer, sheet_name=f"T{id_tienda}_ND", index=False
                    )
                    print(f"Tienda {id_tienda}: sin formulaciones.")
                    continue

                ids = [str(r["idformulacion"]) for r in filas]

                # 2) Traer detalle SIG y tienda solo de esas formulaciones (por chunks)
                sig_rows, tda_rows = [], []
                CHUNK = 800
                for chunk in _chunk_list(ids, CHUNK):
                    ids_str = ",".join("'" + i.replace("'", "''") + "'" for i in chunk)
                    q = q_detalle_template.format(ids=ids_str)
                    cur_sig.execute(q)
                    sig_rows.extend(cur_sig.fetchall())
                    cur_tda.execute(q)
                    tda_rows.extend(cur_tda.fetchall())

                cols = [d[0] for d in cur_sig.description] if cur_sig.description else [
                    "idformulacion", "Formula", "id_Insumo", "Insumo", "Cantidad", "Unidad", "Almacen"
                ]
                df_sig = pd.DataFrame(sig_rows, columns=cols)
                df_tda = pd.DataFrame(tda_rows, columns=cols)

                # limpieza estricta
                df_sig = limpiar_df(df_sig)
                df_tda = limpiar_df(df_tda)

                if df_sig.empty and df_tda.empty:
                    pd.DataFrame([{"Mensaje": "Sin detalle para las formulaciones"}]).to_excel(
                        writer, sheet_name=f"T{id_tienda}_ND2", index=False
                    )
                    print(f"Tienda {id_tienda}: sin detalle.")
                    continue

                # 3) Merge externo por (idformulacion, id_Insumo)
                merged = pd.merge(
                    df_sig, df_tda,
                    how="outer",
                    on=["idformulacion", "id_Insumo"],
                    indicator=True,
                    suffixes=("_SIG", "_TDA")
                )

                # 4) Normalizar columnas resultantes
                merged["Formula"] = merged.get("Formula_SIG").fillna(merged.get("Formula_TDA"))
                merged["Insumo"]  = merged.get("Insumo_SIG").fillna(merged.get("Insumo_TDA"))

                for c in ["Cantidad", "Unidad", "Almacen"]:
                    merged[f"{c}_SIG"] = merged.get(f"{c}_SIG")
                    merged[f"{c}_TDA"] = merged.get(f"{c}_TDA")

                def norm_num(v):
                    try:
                        return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                    except Exception:
                        return Decimal("0.0000")
                def norm_txt(v):
                    return str(v).strip().upper() if v is not None and pd.notna(v) else ""

                def _status_row(r):
                    if r["_merge"] == "left_only":
                        return "Figura_solo_en_SIG"
                    if r["_merge"] == "right_only":
                        return "Figura_solo_en_TDA"
                    if (
                        norm_num(r.get("Cantidad_SIG")) != norm_num(r.get("Cantidad_TDA")) or
                        norm_txt(r.get("Unidad_SIG"))   != norm_txt(r.get("Unidad_TDA")) or
                        norm_txt(r.get("Almacen_SIG"))  != norm_txt(r.get("Almacen_TDA"))
                    ):
                        return "diferencia_en_valores"
                    return "match"

                merged["status"] = merged.apply(_status_row, axis=1)
                out = merged[merged["status"] != "match"].copy()

                if out.empty:
                    # pd.DataFrame([{"Mensaje": "Sin diferencias"}]).to_excel(
                    #     writer, sheet_name=f"T{id_tienda}_OK", index=False
                    # )
                    print(f"Tienda {id_tienda}: sin diferencias.")
                    continue

                # columnas finales y orden
                out.insert(0, "Tienda", id_tienda)
                desired = [
                    "Tienda", "idformulacion", "Formula", "id_Insumo", "Insumo",
                    "Cantidad_SIG", "Cantidad_TDA",
                    "Unidad_SIG", "Unidad_TDA",
                    "Almacen_SIG", "Almacen_TDA",
                    "status"
                ]
                for c in desired:
                    if c not in out.columns:
                        out[c] = pd.NA
                out = out[desired]

                # escribir hoja
                sheet_name = f"T{id_tienda}_diff"
                if len(sheet_name) > 31:
                    sheet_name = sheet_name[:31]
                out.to_excel(writer, sheet_name=sheet_name, index=False)

                # -------------------------
                # FORMATO CONDICIONAL (colorear filas según 'status')
                # -------------------------
                workbook = writer.book
                worksheet = writer.sheets[sheet_name]
                rows = len(out)
                cols_count = len(out.columns)
                if rows > 0:
                    # índices 0-based para xlsxwriter
                    first_row = 1
                    last_row = rows

                    # obtener índice de la columna 'status' y su letra Excel
                    status_idx = out.columns.get_loc("status")
                    status_col_letter = _col_idx_to_excel(status_idx)

                    fmt_red = workbook.add_format({"bg_color": "#FFC7CE"})
                    fmt_blue = workbook.add_format({"bg_color": "#C6E0FF"})
                    fmt_yellow = workbook.add_format({"bg_color": "#FFEB9C"})

                    # fórmulas: columna fija, fila relativa (usa row 2 para primer dato)
                    f_red = f'=${status_col_letter}2="Figura_solo_en_SIG"'
                    f_blue = f'=${status_col_letter}2="Figura_solo_en_TDA"'
                    f_yellow = f'=${status_col_letter}2="diferencia_en_valores"'

                    worksheet.conditional_format(first_row, 0, last_row, cols_count - 1,
                        {"type": "formula", "criteria": f_red, "format": fmt_red})
                    worksheet.conditional_format(first_row, 0, last_row, cols_count - 1,
                        {"type": "formula", "criteria": f_blue, "format": fmt_blue})
                    worksheet.conditional_format(first_row, 0, last_row, cols_count - 1,
                        {"type": "formula", "criteria": f_yellow, "format": fmt_yellow})

                print(f"Tienda {id_tienda}: {len(out)} diferencias registradas.")

            except Exception as e:
                print(f"❌ Error Tienda {id_tienda}: {e}")
                pd.DataFrame([{"Error": str(e)}]).to_excel(
                    writer, sheet_name=f"T{id_tienda}_Error", index=False
                )
            finally:
                try: cur_sig.close(); conn_sig.close()
                except: pass
                try: cur_tda.close(); conn_tda.close()
                except: pass

    print(f"\n✅ Archivo generado: {ruta}")
    return str(ruta)
