import os
import threading
import uuid
from datetime import datetime
from tkinter import messagebox

import pandas as pd

from config.db import get_local_db_connection
from gui.progress_window import ProgressWindow


_INSERT_SQL = """
    INSERT INTO incidencias_salidas
      (lote_id, fecha_carga, sociedad, fecha_proceso,
       item_code, id_tienda, whs_code, tipo_incidencia)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""


def exportar_excel(df_fn, soc_sel: str) -> None:
    """
    Genera un archivo XLSX con los ajustes agrupados por fecha.

    Args:
        df_fn: callable sin argumentos que retorna el DataFrame filtrado activo.
        soc_sel: nombre de la sociedad (usado en el nombre del archivo).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"ajustes_{soc_sel[:10].strip()}_{timestamp}.xlsx"
    path      = os.path.join("SincroSIG", "logs", "SAP", "ConciliacionesSAP", filename)

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df_export = df_fn()

        with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
            workbook         = writer.book
            total_format     = workbook.add_format({'bold': True, 'bg_color': '#FFFF00', 'border': 1})
            num_format       = workbook.add_format({'num_format': '#,##0.0000', 'border': 1})
            num_total_format = workbook.add_format({'bold': True, 'bg_color': '#FFFF00',
                                                    'num_format': '#,##0.0000', 'border': 1})
            header_format    = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})

            cols_final = [
                "ItemCode", "Fecha", "Concepto", "Monto_A_Ingresar",
                "Costo_SIG", "WhsCode", "Centro_Costo", "ID_SIG",
                "Stock_A_Fecha", "Stock_SIG", "Movimiento", "ID_Movimiento",
            ]

            for fg in sorted(df_export['Fecha_Grupo'].unique()):
                sheet_name = str(fg).replace("/", "-")[:31]
                if not sheet_name or sheet_name == "nan":
                    sheet_name = "Ajuste"
                df_sheet  = df_export[df_export['Fecha_Grupo'] == fg].copy()
                worksheet = workbook.add_worksheet(sheet_name)

                for col_num, value in enumerate(cols_final):
                    worksheet.write(0, col_num, value, header_format)

                current_row = 1
                for (id_sig, item_code), df_group in df_sheet.groupby(['ID_SIG', 'ItemCode'], sort=False):
                    try:
                        tienda_fmt = f"P{int(id_sig):04d}"
                    except Exception:
                        tienda_fmt = str(id_sig)

                    for _, data in df_group.iterrows():
                        for col_num, col_name in enumerate(cols_final):
                            if col_name == "Centro_Costo":
                                worksheet.write(current_row, col_num, "C0001")
                            elif col_name == "ID_SIG":
                                worksheet.write(current_row, col_num, tienda_fmt)
                            else:
                                val = data.get(col_name, "")
                                if pd.isna(val):
                                    worksheet.write(current_row, col_num, "")
                                elif isinstance(val, (int, float)):
                                    worksheet.write(current_row, col_num, val, num_format)
                                else:
                                    worksheet.write(current_row, col_num, str(val))
                        current_row += 1

                    total_monto = df_group['Monto_A_Ingresar'].sum()
                    if pd.isna(total_monto):
                        total_monto = 0.0
                    whs_group = str(df_group.iloc[0]['WhsCode'])

                    worksheet.write(current_row, 0,  item_code,         total_format)
                    worksheet.write(current_row, 1,  "-",               total_format)
                    worksheet.write(current_row, 2,  "SUMATORIA TOTAL", total_format)
                    worksheet.write(current_row, 3,  total_monto,       num_total_format)
                    worksheet.write(current_row, 4,  "-",               total_format)
                    worksheet.write(current_row, 5,  whs_group,         total_format)
                    worksheet.write(current_row, 6,  "C0001",           total_format)
                    worksheet.write(current_row, 7,  tienda_fmt,        total_format)
                    worksheet.write(current_row, 8,  "-",               total_format)
                    worksheet.write(current_row, 9,  "-",               total_format)
                    worksheet.write(current_row, 10, "-",               total_format)
                    worksheet.write(current_row, 11, "-",               total_format)
                    current_row += 2

                worksheet.set_column(0, 11, 18)

        messagebox.showinfo("Éxito", f"Archivo de auditoría guardado:\n{filename}")
    except Exception as e:
        messagebox.showerror("Error", f"Fallo al exportar: {e}")


def migrar_bd_local(df_ajustes: pd.DataFrame, soc_sel: str, parent_widget, on_success=None) -> None:
    """
    Inserta los ajustes en la tabla local incidencias_salidas en un hilo de fondo.

    Args:
        df_ajustes:    DataFrame con todos los ajustes a migrar.
        soc_sel:       nombre de la sociedad (guardado como columna 'sociedad').
        parent_widget: widget Tk usado para anclar ProgressWindow y mensajes after().
        on_success:    callback opcional sin argumentos, llamado tras inserción exitosa.
    """
    progress = ProgressWindow(parent_widget, "Migrando a BD local...")

    def _tarea():
        try:
            conn, cur = get_local_db_connection()
            lote_id    = str(uuid.uuid4())
            fecha_carga = datetime.now()
            rows = []
            for _, row in df_ajustes.iterrows():
                raw_fecha = str(row.get('Fecha', ''))
                fecha_p   = (raw_fecha[:10]
                             if raw_fecha[:10] not in ('SIN FECHA', 'S/F', 'Ajust')
                             and len(raw_fecha) >= 10
                             else None)
                try:
                    id_tienda_fmt = f"P{int(row['ID_SIG']):04d}"
                except Exception:
                    id_tienda_fmt = str(row['ID_SIG'])

                concepto_txt = str(row.get('Concepto', ''))
                if 'NIVELACI' in concepto_txt.upper():
                    tipo_inc = 'NIVELACION'
                elif bool(row.get('Is_Primary', True)):
                    tipo_inc = 'COLA_PRIMARIA'
                else:
                    tipo_inc = 'COLA_SECUNDARIA'

                rows.append((
                    lote_id, fecha_carga, soc_sel, fecha_p,
                    str(row['ItemCode']), id_tienda_fmt, str(row['WhsCode']),
                    tipo_inc,
                ))

            cur.executemany(_INSERT_SQL, rows)
            conn.commit()
            cur.close()
            conn.close()

            parent_widget.after(0, lambda n=len(rows), lid=lote_id: messagebox.showinfo(
                "Migración exitosa",
                f"{n} registros insertados en 'incidencias_salidas'.\n\n"
                f"Lote ID: {lid}\n\n"
                f"Puedes conectar Power BI a la tabla 'incidencias_salidas'."
            ))
            if on_success:
                parent_widget.after(0, on_success)
        except Exception as e:
            parent_widget.after(0, lambda m=str(e): messagebox.showerror(
                "Error BD", f"No se pudo migrar:\n{m}"
            ))
        finally:
            progress.close()

    threading.Thread(target=_tarea, daemon=True).start()
