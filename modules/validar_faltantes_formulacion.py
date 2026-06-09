import os
import pandas as pd
from datetime import datetime
from config.db import get_connections, get_store_connection

def validar_faltantes_formulacion_varias(
    tiendas: list[int],
    nombre_archivo: str | None = None
):
    """
    Genera UN solo archivo Excel con 2 pestañas:
      - EnTiendaNoEnSIG  (acumula todas las tiendas)
      - EnSIGNoEnTienda  (acumula todas las tiendas)
    Guardado en SincroSIG/logs/formulaciones/<nombre_archivo>
    """
    base_dir = os.path.join("SincroSIG", "logs", "formulaciones")
    os.makedirs(base_dir, exist_ok=True)

    # Ruta final del archivo
    if not nombre_archivo:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nombre_archivo = f"faltantes_formulacion_{timestamp}.xlsx"

    ruta_archivo = os.path.join(base_dir, nombre_archivo)
    
    # DataFrames acumuladores
    all_en_tienda_no_sig = []
    all_en_sig_no_tienda = []

    for id_tienda in tiendas:
        conn_sig, cur_sig, _, _ = get_connections()
        conn_tda, cur_tda = get_store_connection(id_tienda)
        try:
            query = f"""
                 SELECT
                    f.idformulacion,
                    f.batch,
                    f.idtienda,
                    f.costoformula,
                    f.idunidadmed,
                    f.descripcion,
                    f.nivelformulacion,
                    f.activo,
                    f.idarticulos,
                    f.produccion,
                    p.estado AS precio_estado
                FROM formulacion f
                INNER JOIN formulaciondet fd
                    ON fd.idformulacion = f.idformulacion
                LEFT JOIN preciart p
                    ON p.idarticulos = f.idarticulos
                AND p.estado = 1
                WHERE f.idtienda = {id_tienda}
                  AND f.activo = 1
                GROUP BY f.idformulacion
                ORDER BY f.idarticulos * 1
            """

            # Datos SIG
            cur_sig.execute(query)
            cols_sig = [d[0] for d in cur_sig.description]
            df_sig = pd.DataFrame(cur_sig.fetchall(), columns=cols_sig)

            # Datos Tienda
            cur_tda.execute(query)
            cols_tda = [d[0] for d in cur_tda.description]
            df_tda = pd.DataFrame(cur_tda.fetchall(), columns=cols_tda)

            # Diferencias
            faltan_en_sig = (
                df_tda[~df_tda["idformulacion"].isin(df_sig["idformulacion"])]
                if not df_tda.empty else pd.DataFrame(columns=cols_tda)
            )
            faltan_en_tienda = (
                df_sig[~df_sig["idformulacion"].isin(df_tda["idformulacion"])]
                if not df_sig.empty else pd.DataFrame(columns=cols_sig)
            )

            # Añadir columna de tienda para identificar el origen
            if not faltan_en_sig.empty:
                faltan_en_sig = faltan_en_sig.copy()
                faltan_en_sig["tienda_origen"] = id_tienda
                all_en_tienda_no_sig.append(faltan_en_sig)

            if not faltan_en_tienda.empty:
                faltan_en_tienda = faltan_en_tienda.copy()
                faltan_en_tienda["tienda_origen"] = id_tienda
                all_en_sig_no_tienda.append(faltan_en_tienda)

            print(
                f"Tienda {id_tienda}: "
                f"{len(faltan_en_sig)} enTiendaNoEnSIG | "
                f"{len(faltan_en_tienda)} enSIGNoEnTienda"
            )

        finally:
            cur_sig.close(); conn_sig.close()
            cur_tda.close(); conn_tda.close()

    # Unir los resultados acumulados
    df_all_en_tienda_no_sig = (
        pd.concat(all_en_tienda_no_sig, ignore_index=True)
        if all_en_tienda_no_sig else pd.DataFrame()
    )
    df_all_en_sig_no_tienda = (
        pd.concat(all_en_sig_no_tienda, ignore_index=True)
        if all_en_sig_no_tienda else pd.DataFrame()
    )

    # Crear archivo único con 2 pestañas
    with pd.ExcelWriter(ruta_archivo, engine="xlsxwriter") as writer:
        df_all_en_tienda_no_sig.to_excel(writer,
            sheet_name="EnTiendaNoEnSIG", index=False)
        df_all_en_sig_no_tienda.to_excel(writer,
            sheet_name="EnSIGNoEnTienda", index=False)

    print(f"\nArchivo único generado en: {ruta_archivo}")
