import os
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, filedialog, ttk

import pandas as pd
import pyperclip
import ttkbootstrap as tb

from config.db import get_connections
from config.utils import set_window_icon
from gui.progress_window import ProgressWindow
from gui.widgets.calendar_widget import CampoFecha
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
    win.geometry("820x720")
    set_window_icon(win)

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

    # Estado interno de datos SAP cargados
    _df_sap   = [pd.DataFrame()]
    _n_partes = [0]

    container = tb.Frame(win, padding=16)
    container.pack(fill="both", expand=True)

    # ── Sociedad ──────────────────────────────────────────────────────────────
    tb.Label(container, text="1. Seleccione Sociedad:",
             font=("Segoe UI", 9, "bold")).pack(anchor="w")
    cbo_sociedad = tb.Combobox(container, state="readonly", width=80)
    cbo_sociedad['values'] = [s['rs1'] for s in sociedades]
    cbo_sociedad.pack(pady=(2, 6))

    # ── Rango de fechas ───────────────────────────────────────────────────────
    frame_fechas = tb.LabelFrame(container, text=" 2. Rango de Fechas ")
    frame_fechas.pack(fill="x", pady=(0, 6))

    _hoy  = datetime.now().date()
    _ayer = _hoy - timedelta(days=1)

    tb.Label(frame_fechas, text="Desde:", font=("Segoe UI", 9)).grid(
        row=0, column=0, padx=(10, 2), pady=8)
    ent_desde = CampoFecha(frame_fechas, initialdate=_ayer)
    ent_desde.grid(row=0, column=1, padx=5, pady=8)

    tb.Label(frame_fechas, text="Hasta:", font=("Segoe UI", 9)).grid(
        row=0, column=2, padx=(15, 2))
    ent_hasta = CampoFecha(frame_fechas, initialdate=_ayer)
    ent_hasta.grid(row=0, column=3, padx=5)

    # ── Botón generar query + cargar Excel ────────────────────────────────────
    frame_top_btns = tb.Frame(container)
    frame_top_btns.pack(fill="x", pady=(0, 4))
    tb.Button(frame_top_btns, text="1. Generar Query SAP",
              bootstyle="info",
              command=lambda: func_generar_query()
              ).pack(side="left", expand=True, fill="x", padx=(0, 6))
    tb.Button(frame_top_btns, text="📂 Cargar desde Excel exportado",
              bootstyle="secondary",
              command=lambda: cargar_desde_excel()
              ).pack(side="left", expand=True, fill="x")

    ttk.Separator(container, orient="horizontal").pack(fill="x", pady=(6, 4))

    # ── Sección Data SAP ──────────────────────────────────────────────────────
    sap_frame = tb.LabelFrame(container, text=" 2. Data SAP — pegue los resultados del query ")
    sap_frame.pack(fill="both", expand=True, pady=(0, 4))

    sap_btn_row = tb.Frame(sap_frame, padding=(4, 4, 4, 2))
    sap_btn_row.pack(fill="x")
    tb.Button(sap_btn_row, text="📋 Pegar Parte  (Ctrl+V)", bootstyle="info",
              command=lambda: _pegar_sap()
              ).pack(side="left", expand=True, fill="x", padx=(0, 6))
    tb.Button(sap_btn_row, text="🗑 Limpiar", bootstyle="secondary",
              command=lambda: _limpiar_sap_manual()
              ).pack(side="left")

    lbl_sap_estado = tb.Label(sap_frame, text="Sin datos cargados.",
                               font=("Segoe UI", 9, "italic"), bootstyle="secondary")
    lbl_sap_estado.pack(anchor="w", padx=8, pady=(0, 2))

    sap_tree_frame = tb.Frame(sap_frame, padding=(4, 0, 4, 4))
    sap_tree_frame.pack(fill="both", expand=True)

    sap_cols = ("item", "whs", "stock")
    sap_tree = ttk.Treeview(sap_tree_frame, columns=sap_cols, show="headings", height=8)
    sap_tree.heading("item",  text="Artículo")
    sap_tree.heading("whs",   text="Almacén")
    sap_tree.heading("stock", text="Stock SAP")
    for c in sap_cols:
        sap_tree.column(c, width=240, anchor="center")

    sap_sb = ttk.Scrollbar(sap_tree_frame, orient="vertical", command=sap_tree.yview)
    sap_tree.configure(yscroll=sap_sb.set)
    sap_tree.pack(fill="both", expand=True, side="left")
    sap_sb.pack(fill="y", side="left")

    # ── Botón procesar cruce ───────────────────────────────────────────────────
    btn_procesar = tb.Button(container, text="🚀 Procesar Cruce", bootstyle="success",
                             state="disabled", command=lambda: _do_cruce())
    btn_procesar.pack(fill="x", pady=(4, 6))

    # ── Indicador de sociedades migradas esta sesión ───────────────────────────
    migradas_frame = tk.Frame(container, bg="#0f2a0f", bd=1, relief="solid")
    migradas_frame.pack(fill="x")
    tk.Label(migradas_frame, text="Migradas esta sesión:", bg="#0f2a0f", fg="#aaaaaa",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=(10, 6), pady=(4, 1))
    txt_migradas = tk.Text(
        migradas_frame, bg="#0f2a0f", fg="#555555",
        font=("Segoe UI", 8), height=2, bd=0,
        state="disabled", wrap="none", cursor="arrow",
        selectbackground="#0f2a0f",
    )
    txt_migradas.pack(fill="x", padx=10, pady=(0, 4))
    txt_migradas.tag_config("entry", foreground="#6BCB77")
    tk.Label(migradas_frame, text="—  sin migraciones aún",
             bg="#0f2a0f", fg="#555555", font=("Segoe UI", 8, "italic"),
             name="lbl_placeholder").pack(anchor="w", padx=10, pady=(0, 4))

    # ── Funciones auxiliares SAP ──────────────────────────────────────────────

    def _limpiar_sap_vista():
        for i in sap_tree.get_children():
            sap_tree.delete(i)
        lbl_sap_estado.config(text="Sin datos cargados.")
        btn_procesar.config(state="disabled")

    def _limpiar_sap_manual():
        _df_sap[0] = pd.DataFrame()
        _n_partes[0] = 0
        _limpiar_sap_vista()

    def _refrescar_sap():
        _limpiar_sap_vista()
        for _, row in _df_sap[0].iterrows():
            sap_tree.insert("", "end", values=(
                row.get('ItemCode', 'N/A'),
                row.get('WhsCode',  'N/A'),
                f"{float(row.get('Stock_A_Fecha', 0)):.4f}",
            ))
        n = len(_df_sap[0])
        lbl_sap_estado.config(
            text=f"{n} artículo(s) acumulados  ·  {_n_partes[0]} parte(s) pegada(s)."
        )
        btn_procesar.config(state="normal" if n > 0 else "disabled")

    def _pegar_sap():
        try:
            df_nueva = pd.read_clipboard(sep='\t')
            df_nueva.columns = [c.strip() for c in df_nueva.columns]
            rename_map = {
                'Número de artículo': 'ItemCode',
                'Código de almacén':  'WhsCode',
                'Stock_A_Fecha':      'Stock_A_Fecha',
                'ItemName':           'Descripcion',
            }
            df_nueva = df_nueva.rename(columns=rename_map)
            if 'WhsCode' in df_nueva.columns:
                df_nueva['WhsCode'] = (df_nueva['WhsCode']
                                       .astype(str).str.strip().str.zfill(2))
            if 'Stock_A_Fecha' in df_nueva.columns:
                df_nueva['Stock_A_Fecha'] = (df_nueva['Stock_A_Fecha']
                                              .astype(str).str.replace(',', '')
                                              .astype(float))
            if _df_sap[0].empty:
                _df_sap[0] = df_nueva
            else:
                _df_sap[0] = (pd.concat([_df_sap[0], df_nueva], ignore_index=True)
                              .drop_duplicates(subset=['ItemCode', 'WhsCode'], keep='last'))
            _n_partes[0] += 1
            _refrescar_sap()
        except Exception as e:
            messagebox.showerror("Error", f"Error al leer datos: {e}", parent=win)

    def _on_sociedad_changed(_event=None):
        """Al cambiar de sociedad, limpia los datos SAP cargados para evitar cruces incorrectos."""
        _df_sap[0]   = pd.DataFrame()
        _n_partes[0] = 0
        _limpiar_sap_vista()

    cbo_sociedad.bind("<<ComboboxSelected>>", _on_sociedad_changed)

    def _on_ctrl_v(event):
        focused = win.focus_get()
        try:
            cls = focused.winfo_class() if focused else ""
        except Exception:
            cls = ""
        if cls in ('TEntry', 'TCombobox', 'Entry', 'Combobox', 'Text'):
            return
        _pegar_sap()
        return "break"

    win.bind("<Control-v>", _on_ctrl_v)

    # ── Función procesar cruce ────────────────────────────────────────────────

    def _do_cruce():
        soc = cbo_sociedad.get()
        if not soc:
            messagebox.showwarning("Sociedad requerida",
                                   "Seleccione una sociedad antes de continuar.",
                                   parent=win)
            return
        if _df_sap[0].empty:
            messagebox.showwarning("Sin datos SAP",
                                   "Pegue los resultados del query SAP antes de procesar.",
                                   parent=win)
            return
        _ejecutar_reconciliacion(_df_sap[0].copy(), soc)

    # ── Función generar query ─────────────────────────────────────────────────

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

                from config.constants import DIR_SAP_QUERY
                queries = construir_queries_sap(items_set)
                folder  = guardar_queries(queries, soc_sel, str(DIR_SAP_QUERY))
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

    # ── Función ejecutar reconciliación ───────────────────────────────────────

    def _on_migrado(soc_sel: str):
        try:
            migradas_frame.nametowidget("lbl_placeholder").pack_forget()
        except Exception:
            pass
        timestamp = datetime.now().strftime("%d/%m/%Y  %H:%M")
        txt_migradas.config(state="normal")
        txt_migradas.insert("end", f"✓  {timestamp}  —  {soc_sel}\n", "entry")
        txt_migradas.config(state="disabled")
        txt_migradas.see("end")

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
                        f"Log guardado en:\nDocumentos\\SincroSIGSAP\\SAP\\QuerySAP\\logs_errorparseo\\{nl}"
                    ))

                df_logs = pd.DataFrame(logs_procesados)

                items = list(df_logs['item'].unique()) if not df_logs.empty else []
                df_saldos = cargar_saldos(cur_sig, tiendas_ids, items)

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
                        df_sap_cruce = pd.concat([df_sap_cruce, pd.DataFrame(missing)],
                                                 ignore_index=True)

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
                              mostrar_ventana_resultados(win, f, soc_sel, n,
                                                         on_migrado=_on_migrado))
            except Exception as e:
                win.after(0, lambda m=str(e): messagebox.showerror("Error", m))
            finally:
                progress.close()

        threading.Thread(target=_tarea, daemon=True).start()

    # ── Función cargar desde Excel ─────────────────────────────────────────────

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

                for str_col in ('Concepto', 'ID_Movimiento', 'WhsCode', 'Descripcion'):
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

                for num_col in ('Monto_A_Ingresar', 'Stock_A_Fecha', 'Stock_SIG',
                                'Movimiento', 'Costo_SIG'):
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
