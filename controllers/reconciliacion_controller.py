import os
import threading
from datetime import datetime, timedelta
from tkinter import messagebox, filedialog, ttk

import pandas as pd
import pyperclip
import ttkbootstrap as tb

from config.db import get_connections
from gui.progress_window import ProgressWindow
from gui.widgets.calendar_widget import CampoFecha
from gui.sap_input_window import VentanaEntradaSAP
from gui.reconciliacion_resultados import mostrar_ventana_resultados
from modules.reconciliacion_bd import obtener_sociedades, obtener_tiendas_ids, cargar_logs_bd, cargar_saldos
from modules.reconciliacion_query import (
    parsear_logs_para_query,
    parsear_logs_para_cruce,
    construir_queries_sap,
    guardar_queries,
    escribir_log_parseo,
)
from modules.reconciliacion_sap_service import calcular_ajustes_tres_vias


def abrir_interfaz_reconciliacion(root):
    win = tb.Toplevel(root)
    win.title("Reconciliación de Stock SAP")
    win.geometry("700x500")

    def _on_sociedades_cargadas(sociedades):
        win.after(0, lambda: _construir_ui(win, sociedades))

    def _cargar_sociedades_bg():
        try:
            sociedades = obtener_sociedades()
            _on_sociedades_cargadas(sociedades)
        except Exception as e:
            win.after(0, lambda m=str(e): messagebox.showerror("Error", m))

    threading.Thread(target=_cargar_sociedades_bg, daemon=True).start()


def _construir_ui(win, sociedades: list):
    sociedades_dict = {s['rs1']: s['idempresas'] for s in sociedades}

    container = tb.Frame(win, padding=20)
    container.pack(fill="both", expand=True)

    tb.Label(container, text="1. Seleccione Sociedad:",
             font=("Segoe UI", 9, "bold")).pack(anchor="w")
    cbo_sociedad = tb.Combobox(container, state="readonly", width=70)
    cbo_sociedad['values'] = [s['rs1'] for s in sociedades]
    cbo_sociedad.pack(pady=5)

    # ── Indicador de sociedades migradas esta sesión ───────────────────────────
    import tkinter as tk

    migradas_frame = tk.Frame(container, bg="#0f2a0f", bd=1, relief="solid")
    migradas_frame.pack(fill="x", pady=(2, 0))
    tk.Label(migradas_frame, text="Migradas esta sesión:", bg="#0f2a0f", fg="#aaaaaa",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=(10, 6), pady=(4, 1))
    txt_migradas = tk.Text(
        migradas_frame, bg="#0f2a0f", fg="#555555",
        font=("Segoe UI", 8), height=3, bd=0,
        state="disabled", wrap="none", cursor="arrow",
        selectbackground="#0f2a0f",
    )
    txt_migradas.pack(fill="x", padx=10, pady=(0, 4))
    txt_migradas.tag_config("entry", foreground="#6BCB77")
    tk.Label(migradas_frame, text="—  sin migraciones aún",
             bg="#0f2a0f", fg="#555555", font=("Segoe UI", 8, "italic"),
             name="lbl_placeholder").pack(anchor="w", padx=10, pady=(0, 4))

    def _on_migrado(soc_sel: str):
        # Ocultar placeholder la primera vez
        try:
            migradas_frame.nametowidget("lbl_placeholder").pack_forget()
        except Exception:
            pass
        timestamp = datetime.now().strftime("%d/%m/%Y  %H:%M")
        txt_migradas.config(state="normal")
        txt_migradas.insert("end", f"✓  {timestamp}  —  {soc_sel}\n", "entry")
        txt_migradas.config(state="disabled")
        txt_migradas.see("end")

    frame_fechas = tb.LabelFrame(container, text=" 2. Rango de Fechas ")
    frame_fechas.pack(fill="x", pady=15, padx=10)

    _hoy        = datetime.now().date()
    _ayer       = _hoy - timedelta(days=1)
    _primer_dia = _hoy.replace(day=1)

    tb.Label(frame_fechas, text="Desde:", font=("Segoe UI", 9)).grid(row=0, column=0, padx=(10, 2), pady=10)
    ent_desde = CampoFecha(frame_fechas, initialdate=_ayer)
    ent_desde.grid(row=0, column=1, padx=5, pady=10)

    tb.Label(frame_fechas, text="Hasta:", font=("Segoe UI", 9)).grid(row=0, column=2, padx=(15, 2))
    ent_hasta = CampoFecha(frame_fechas, initialdate=_ayer)
    ent_hasta.grid(row=0, column=3, padx=5)

    # ── Botón 1: Generar Query SAP ─────────────────────────────────────────────
    def func_generar_query():
        soc_sel = cbo_sociedad.get()
        if not soc_sel:
            messagebox.showwarning("Sociedad requerida",
                                   "Seleccione una sociedad antes de continuar.",
                                   parent=win)
            return
        id_emp   = sociedades_dict[soc_sel]
        progress = ProgressWindow(win, "Generando Query SAP (Primarios + Secundarios)...")

        def _tarea():
            try:
                conn_sig, cur_sig, _, _ = get_connections()
                tiendas_ids = obtener_tiendas_ids(id_emp)
                logs        = cargar_logs_bd(cur_sig, tiendas_ids, ent_desde.get(), ent_hasta.get())

                primary_set, secondary_set, errores = parsear_logs_para_query(logs)

                nombre_log = None
                if errores:
                    nombre_log, _ = escribir_log_parseo(soc_sel, errores)

                items_set = primary_set | secondary_set
                if not items_set:
                    aviso = (f"\n\n⚠ {len(errores)} registro(s) omitidos por message no reconocido."
                             f"\nLog: {nombre_log}" if errores else "")
                    win.after(0, lambda a=aviso: messagebox.showinfo(
                        "Info", f"No se encontraron ítems procesables.{a}"
                    ))
                    return

                queries = construir_queries_sap(items_set)
                folder  = guardar_queries(queries, soc_sel, os.path.join("SincroSIG", "logs", "SAP"))
                pyperclip.copy(queries[0])

                n_items, n_partes = len(items_set), len(queries)
                aviso_q = (f"\n\n⚠ {len(errores)} registro(s) omitidos por message no reconocido.\nLog: {nombre_log}"
                           if errores else "")
                if n_partes == 1:
                    msg = (f"[Primarios + Secundarios] Query copiado al portapapeles.\n"
                           f"{n_items} artículo(s) únicos.\nGuardado en: {folder}{aviso_q}")
                else:
                    msg = (f"[Primarios + Secundarios] Query dividido en {n_partes} partes.\n"
                           f"{n_items} artículos únicos en total.\n"
                           f"Parte 1/{n_partes} copiada al portapapeles.\n"
                           f"Ejecute cada parte en SAP por separado.\nArchivos en: {folder}{aviso_q}")
                win.after(0, lambda m=msg: messagebox.showinfo("Éxito", m))
            except Exception as e:
                win.after(0, lambda m=str(e): messagebox.showerror("Error", m))
            finally:
                progress.close()

        threading.Thread(target=_tarea, daemon=True).start()

    # ── Botón 2: Cargar SAP y Cruzar ──────────────────────────────────────────
    _ref_entrada = [None]

    def lanzar_cruce():
        soc = cbo_sociedad.get()
        if not soc:
            messagebox.showwarning("Sociedad requerida",
                                   "Seleccione una sociedad antes de continuar.",
                                   parent=win)
            return
        if _ref_entrada[0] is not None and _ref_entrada[0].winfo_exists():
            _ref_entrada[0].lift()
            _ref_entrada[0].focus_force()
            return
        ventana = VentanaEntradaSAP(win, lambda df: _ejecutar_reconciliacion(df, soc))
        _ref_entrada[0] = ventana

    def _ejecutar_reconciliacion(df_sap: pd.DataFrame, soc_sel: str):
        progress = ProgressWindow(win, "Realizando Auditoría...")

        def _tarea():
            try:
                conn_sig, cur_sig, _, _ = get_connections()
                id_emp      = sociedades_dict[soc_sel]
                tiendas_ids = obtener_tiendas_ids(id_emp)
                logs        = cargar_logs_bd(cur_sig, tiendas_ids, ent_desde.get(), ent_hasta.get())

                logs_procesados, errores = parsear_logs_para_cruce(logs)

                if errores:
                    nombre_log_c, _ = escribir_log_parseo(soc_sel, errores)
                    win.after(0, lambda n=len(errores), nl=nombre_log_c: messagebox.showwarning(
                        "Registros omitidos",
                        f"{n} registro(s) omitidos por message no reconocido.\n"
                        f"Log guardado en:\nlogs/SAP/logs_errorparseo/{nl}"
                    ))

                df_logs = pd.DataFrame(logs_procesados)

                items = list(df_logs['item'].unique()) if not df_logs.empty else []
                df_saldos = cargar_saldos(cur_sig, tiendas_ids, items)

                # Ítems del log ausentes en el paste SAP → stock = 0
                df_sap_cruce = df_sap.copy()
                if not df_logs.empty:
                    sap_keys = set(zip(
                        df_sap_cruce['ItemCode'].astype(str).str.strip(),
                        df_sap_cruce['WhsCode'].astype(str).str.strip().str.zfill(2)
                    ))
                    missing = [
                        {'ItemCode': str(r['item']), 'WhsCode': str(r['whs']), 'Stock_A_Fecha': 0.0}
                        for _, r in df_logs[['item', 'whs']].drop_duplicates().iterrows()
                        if (str(r['item']), str(r['whs'])) not in sap_keys
                    ]
                    if missing:
                        df_sap_cruce = pd.concat([df_sap_cruce, pd.DataFrame(missing)], ignore_index=True)

                df_final = calcular_ajustes_tres_vias(df_sap_cruce, df_logs, df_saldos)

                if not df_final.empty:
                    df_costos = (df_saldos[['ItemCode', 'idtienda', 'costoprom']]
                                 .rename(columns={'idtienda': 'ID_SIG', 'costoprom': 'Costo_SIG'}))
                    df_final  = df_final.merge(df_costos, on=['ItemCode', 'ID_SIG'], how='left')
                    df_final['Fecha']       = df_final['Fecha'].fillna("S/F")
                    df_final['Fecha_Grupo'] = df_final.groupby(['ID_SIG', 'ItemCode'])['Fecha'].transform(
                        lambda x: x.iloc[0] if x.iloc[0] != "SIN FECHA" else "Ajuste"
                    )
                    df_final = df_final.sort_values(
                        by=['Fecha_Grupo', 'ID_SIG', 'ItemCode', 'Prioridad', 'Fecha']
                    )

                n_logs_bd = len(logs)
                if df_final.empty:
                    win.after(0, lambda: messagebox.showinfo("Info", "Sin diferencias."))
                else:
                    win.after(0, lambda f=df_final, n=n_logs_bd:
                              mostrar_ventana_resultados(win, f, soc_sel, n, on_migrado=_on_migrado))
            except Exception as e:
                win.after(0, lambda m=str(e): messagebox.showerror("Error", m))
            finally:
                progress.close()

        threading.Thread(target=_tarea, daemon=True).start()

    # ── Botón 3: Cargar desde Excel ────────────────────────────────────────────
    def cargar_desde_excel():
        path = filedialog.askopenfilename(
            title="Seleccionar Excel de Auditoría exportado",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not path:
            return
        try:
            xl  = pd.ExcelFile(path)
            dfs = []
            for sheet in xl.sheet_names:
                df_s = xl.parse(sheet)
                if df_s.empty:
                    continue

                if 'ItemCode' in df_s.columns:
                    df_s = df_s[~df_s['ItemCode'].astype(str).str.startswith('TOTAL')]
                    df_s = df_s.dropna(subset=['ItemCode'])
                    df_s = df_s[df_s['ItemCode'].astype(str).str.strip() != '']
                if 'Concepto' in df_s.columns:
                    df_s = df_s[df_s['Concepto'].astype(str) != 'SUMATORIA TOTAL']
                if df_s.empty:
                    continue

                for str_col in ('Concepto', 'ID_Movimiento', 'WhsCode'):
                    if str_col in df_s.columns:
                        df_s[str_col] = df_s[str_col].fillna('').astype(str).str.strip()

                if 'Fecha' in df_s.columns:
                    df_s['Fecha'] = (pd.to_datetime(df_s['Fecha'], errors='coerce')
                                     .dt.strftime('%Y-%m-%d')
                                     .fillna(''))

                if 'ID_SIG' in df_s.columns:
                    df_s['ID_SIG'] = (df_s['ID_SIG'].fillna('').astype(str).str.strip()
                                      .str.replace(r'\.0$', '', regex=True)
                                      .str.replace(r'^P0*', '', regex=True))

                df_s['Fecha_Grupo'] = sheet

                if 'Is_Primary' not in df_s.columns:
                    df_s['Is_Primary'] = ~df_s['Concepto'].str.contains('NIVELACIÓN', na=False)
                if 'Prioridad' not in df_s.columns:
                    df_s['Prioridad'] = df_s['Concepto'].apply(
                        lambda c: 0 if 'NIVELACIÓN' in str(c) else 1
                    )

                for num_col in ('Monto_A_Ingresar', 'Stock_A_Fecha', 'Stock_SIG', 'Movimiento', 'Costo_SIG'):
                    if num_col in df_s.columns:
                        df_s[num_col] = pd.to_numeric(df_s[num_col], errors='coerce').fillna(0.0)

                dfs.append(df_s)

            if not dfs:
                messagebox.showwarning("Sin datos", "No se encontraron datos válidos en el archivo.")
                return

            df_combined = (pd.concat(dfs, ignore_index=True)
                           .sort_values(
                               by=['Fecha_Grupo', 'ID_SIG', 'ItemCode', 'Prioridad', 'Fecha'],
                               ignore_index=True
                           ))

            nombre_archivo = os.path.basename(path)
            partes         = nombre_archivo.replace('ajustes_', '').rsplit('_', 2)
            soc_nombre     = partes[0] if len(partes) >= 2 else nombre_archivo

            mostrar_ventana_resultados(win, df_combined, soc_nombre)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el archivo:\n{e}")

    # ── Layout de botones ──────────────────────────────────────────────────────
    frame_queries = tb.Frame(container)
    frame_queries.pack(fill="x", pady=(8, 2))
    tb.Button(frame_queries, text="1. Generar Query SAP",
              command=func_generar_query, bootstyle="info"
              ).pack(side="left", expand=True, fill="x")
    tb.Button(container, text="2. Cargar SAP y Cruzar",
              command=lanzar_cruce, bootstyle="success").pack(fill="x", pady=(2, 0))

    ttk.Separator(container, orient="horizontal").pack(fill="x", pady=(14, 6))

    tb.Button(container, text="📂 Cargar desde Excel exportado",
              command=cargar_desde_excel, bootstyle="secondary").pack(fill="x", pady=(0, 4))
