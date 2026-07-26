import tkinter as tk
from tkinter import ttk, font as tkfont
import ttkbootstrap as tb
import pandas as pd
import pyperclip

from modules.reconciliacion_export import exportar_excel, migrar_bd_local
from gui.diagnostico_panel import abrir_panel_diagnostico
from config.utils import set_window_icon


_COLS    = ("item",     "descrip",       "fecha",      "concepto", "ajuste",           "costo_sig",        "whs",     "centro_costo",    "id_sig",  "stock_sap",  "stock_sig",  "mov",          "id_mov")
_HEADERS = ["Artículo", "Descripción",   "Fecha Reg.", "Concepto", "Cant. a Ingresar", "Precio Unit. SIG", "Almacén", "Centro de Costo", "Tienda",  "Stock SAP",  "Stock SIG",  "Cant. Salida", "ID Mov"]
_WIDTHS  = [140,        200,             100,          215,        120,                110,                75,        110,               90,        110,          110,          100,            95]

# Colores compartidos entre leyenda y tags del Treeview
_COL_NIV  = "#F0D060"  # amarillo dorado — NIVELACIÓN
_COL_PRIM = "#5DC87A"  # verde medio     — COLA Primaria
_COL_SEC  = "#E8973A"  # naranja         — COLA Secundaria
_COL_SEL  = "#2962A8"  # azul selección  — highlight al copiar columna


def mostrar_ventana_resultados(parent, df_ajustes, soc_sel: str, n_logs_bd: int = 0, on_migrado=None):
    _totales_grupo = df_ajustes.groupby(['ID_SIG', 'ItemCode'])['Monto_A_Ingresar'].transform('sum')
    df_ajustes = df_ajustes[_totales_grupo.round(4) > 0].copy()

    top = tb.Toplevel(parent)
    top.title(f"Panel de Ajustes Directo SAP - {soc_sel}")
    top.geometry("1450x750")
    set_window_icon(top)

    def on_closing():
        nonlocal df_ajustes
        df_ajustes = None
        top.destroy()
    top.protocol("WM_DELETE_WINDOW", on_closing)

    # btn_frame debe empaquetarse ANTES que main_frame para que siempre sea visible
    btn_frame = tb.Frame(top)
    btn_frame.pack(side="bottom", fill="x", padx=10, pady=10)

    main_frame = tb.Frame(top, padding=10)
    main_frame.pack(fill="both", expand=True)

    # ── Filtros ────────────────────────────────────────────────────────────────
    header_frame = tb.Frame(main_frame)
    header_frame.pack(fill="x", pady=(0, 4))
    tb.Label(header_frame, text="Resumen de Reconciliación por Fechas",
             font=("Segoe UI", 12, "bold"), bootstyle="primary").pack(side="left")

    var_ocultar_sin_ingreso = tk.BooleanVar(value=True)
    var_ocultar_stock_ok    = tk.BooleanVar(value=True)
    var_expandir_todo       = tk.BooleanVar(value=False)
    trees = []

    tb.Checkbutton(header_frame, text="Ocultar artículos con ingreso total = 0",
                   variable=var_ocultar_sin_ingreso, bootstyle="secondary",
                   command=lambda: construir_tabs(_df_activo())).pack(side="right", padx=6)
    tb.Checkbutton(header_frame, text="Ocultar artículos con stock SAP suficiente",
                   variable=var_ocultar_stock_ok, bootstyle="secondary",
                   command=lambda: construir_tabs(_df_activo())).pack(side="right", padx=2)

    def toggle_expand_all():
        state = var_expandir_todo.get()
        for t in trees:
            if t.winfo_exists():
                for iid in t.get_children():
                    t.item(iid, open=state)
    tb.Checkbutton(header_frame, text="Expandir todo",
                   variable=var_expandir_todo, bootstyle="info",
                   command=toggle_expand_all).pack(side="right", padx=6)

    # ── Auditoría ──────────────────────────────────────────────────────────────
    _cola_df = df_ajustes[df_ajustes['Concepto'].str.contains('COLA', na=False)]
    _niv_df  = df_ajustes[df_ajustes['Concepto'].str.contains('NIVELACIÓN', na=False)]
    _n_prim  = len(_cola_df[_cola_df['Is_Primary'].eq(True)]) if 'Is_Primary' in _cola_df.columns else 0
    _n_sec   = len(_cola_df[_cola_df['Is_Primary'].eq(False)]) if 'Is_Primary' in _cola_df.columns else 0
    _n_art_n = _niv_df['ItemCode'].nunique()

    audit_frame = tk.Frame(main_frame, bg="#1a1a2e", bd=1, relief="solid")
    audit_frame.pack(fill="x", pady=(0, 6))

    def _stat(parent, etiqueta, valor, color, bg="#1a1a2e", sep=True):
        tk.Label(parent, text=etiqueta, bg=bg, fg="#aaaaaa",
                 font=("Segoe UI", 8)).pack(side="left", padx=(12, 2), pady=5)
        tk.Label(parent, text=str(valor), bg=bg, fg=color,
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 12), pady=5)
        if sep:
            tk.Frame(parent, bg="#444455", width=1).pack(side="left", fill="y", pady=4)

    _stat(audit_frame, "Registros BD procesados:", n_logs_bd, "#FFFFFF")
    _stat(audit_frame, "COLA primarios (message):", _n_prim,  "#FF6B6B")
    _stat(audit_frame, "COLA secundarios:",          _n_sec,   "#7EB8F7")
    _stat(audit_frame, "NIVELACIÓN:",                _n_art_n, "#6BCB77", sep=False)

    # ── Notebook ───────────────────────────────────────────────────────────────
    notebook = tb.Notebook(main_frame, bootstyle="info")
    notebook.pack(fill="both", expand=True, pady=5)

    style = ttk.Style()
    for tab_style in ("TNotebook.Tab", "info.TNotebook.Tab"):
        style.map(tab_style,
                  foreground=[("selected", "#FFFFFF"), ("!selected", "#1a1a1a")])

    def _df_activo():
        df = df_ajustes.copy()
        if var_ocultar_sin_ingreso.get():
            totales = df.groupby(['ID_SIG', 'ItemCode'])['Monto_A_Ingresar'].transform('sum')
            df = df[totales > 0]
        if var_ocultar_stock_ok.get():
            df_cola = df[df['Concepto'].str.contains('COLA', na=False)]
            if not df_cola.empty:
                totals = df_cola.groupby(['ID_SIG', 'ItemCode']).agg(
                    total_exits=('Movimiento',    'sum'),
                    stock_sap  =('Stock_A_Fecha', 'first'),
                )
                grupos_cubiertos = totals[totals['total_exits'] <= totals['stock_sap']].index
                mi = pd.MultiIndex.from_arrays([df['ID_SIG'], df['ItemCode']])
                df = df[~mi.isin(grupos_cubiertos)]
        return df.copy()

    def construir_tabs(df):
        trees.clear()
        for tab_id in notebook.tabs():
            notebook.forget(tab_id)

        if df is None or df.empty:
            f = tb.Frame(notebook, padding=20)
            notebook.add(f, text=" Sin registros ")
            tb.Label(f, text="No hay registros con los filtros aplicados.",
                     font=("Segoe UI", 10)).pack(pady=30)
            return

        for fg in sorted(df['Fecha_Grupo'].unique()):
            tab_name  = str(fg).replace("/", "-")
            tab_frame = tb.Frame(notebook, padding=5)
            notebook.add(tab_frame, text=f" Fecha: {tab_name} ")

            # ── Leyenda — Canvas con rectángulo dibujado para que el color
            # no sea sobreescrito por el sistema de temas de ttkbootstrap.
            legend_frame = tb.Frame(tab_frame)
            legend_frame.pack(fill="x", pady=(0, 4))
            _chip_font = tkfont.Font(family="Segoe UI", size=8, weight="bold")
            for _color, _texto in [
                (_COL_NIV,  "  NIVELACIÓN  "),
                (_COL_PRIM, "  COLA Primaria  "),
                (_COL_SEC,  "  COLA Secundaria  "),
            ]:
                _tw = _chip_font.measure(_texto) + 4
                _th = 22
                _cv = tk.Canvas(legend_frame, width=_tw, height=_th,
                                bd=0, highlightthickness=0)
                _cv.create_rectangle(0, 0, _tw, _th, fill=_color, outline="")
                _cv.create_text(_tw // 2, _th // 2, text=_texto,
                                fill="#FFFFFF", font=("Segoe UI", 8, "bold"),
                                anchor="center")
                _cv.pack(side="left", padx=4, pady=2)

            lbl_status = tk.Label(
                tab_frame,
                text="▲ Clic en un encabezado para copiar esa columna",
                bg="#1a1a2e", fg="#aaaaaa", font=("Segoe UI", 8), anchor="w"
            )
            lbl_status.pack(fill="x", padx=6, pady=(2, 2))

            tree_container = tb.Frame(tab_frame)
            tree_container.pack(fill="both", expand=True)

            tree = ttk.Treeview(tree_container, columns=_COLS, show="tree headings", height=20)
            tree.column("#0", width=26, stretch=False, minwidth=26)
            tree.tk.call("ttk::style", "configure", "Treeview", "-rowheight", 25)
            tree.tk.call("ttk::style", "configure", "Treeview", "-font", ("Segoe UI", 9))
            tree.tk.call("ttk::style", "configure", "Treeview.Heading", "-font", ("Segoe UI", 9, "bold"))

            def _cmd_copiar(t, lbl, idx, nombre_col, col_id):
                def _copiar():
                    top_iids = list(t.get_children())

                    # Toplevel translucente — resalta solo las celdas de la columna sin ocultar el texto
                    _overlay = [None]
                    visible = [iid for iid in top_iids if t.bbox(iid)]
                    if visible:
                        try:
                            raw = t.bbox(visible[0], col_id)
                            if raw:
                                cx, cy0, cw, _ = raw
                                ch = t.winfo_height() - cy0
                                if ch > 0 and cw > 0:
                                    sx = t.winfo_rootx() + cx
                                    sy = t.winfo_rooty() + cy0
                                    ov = tk.Toplevel(t)
                                    ov.overrideredirect(True)
                                    ov.geometry(f"{cw}x{ch}+{sx}+{sy}")
                                    ov.configure(bg=_COL_SEL)
                                    ov.attributes("-alpha", 0.30)
                                    _overlay[0] = ov
                        except Exception:
                            pass

                    # Copiar valores de las filas top-level
                    valores = []
                    for iid in top_iids:
                        vals = t.item(iid, 'values')
                        if vals and idx < len(vals):
                            v = str(vals[idx]).strip()
                            if v and v != "-":
                                valores.append(v)
                    if valores:
                        pyperclip.copy("\n".join(valores))
                        lbl.config(
                            text=f"✓  '{nombre_col}' copiada — {len(valores)} filas al portapapeles",
                            fg="#6BCB77",
                        )
                    else:
                        lbl.config(text="Sin datos para copiar.", fg="#FF6B6B")

                    def _restore():
                        if _overlay[0]:
                            try:
                                _overlay[0].destroy()
                            except Exception:
                                pass
                    t.after(1200, _restore)

                return _copiar

            for i, (col, head, w) in enumerate(zip(_COLS, _HEADERS, _WIDTHS)):
                tree.heading(col, text=head,
                             command=_cmd_copiar(tree, lbl_status, i, head, col))
                tree.column(col, width=w, anchor="center")

            sb_v = ttk.Scrollbar(tree_container, orient="vertical",  command=tree.yview)
            sb_h = ttk.Scrollbar(tab_frame,      orient="horizontal", command=tree.xview)
            tree.configure(yscroll=sb_v.set, xscroll=sb_h.set)
            tree.pack(fill="both", expand=True, side="left")
            sb_v.pack(fill="y", side="left")
            sb_h.pack(fill="x", side="bottom")

            tree.tag_configure('nivelacion', background=_COL_NIV,  foreground="black", font=('Segoe UI', 9, 'bold'))
            tree.tag_configure('cola_prim',  background=_COL_PRIM, foreground="black", font=('Segoe UI', 9, 'bold'))
            tree.tag_configure('cola_sec',   background=_COL_SEC,  foreground="black", font=('Segoe UI', 9, 'bold'))
            tree.tag_configure('total_row',  background="#000000",  foreground="white", font=('Segoe UI', 12, 'bold'))

            df_sheet = df[df['Fecha_Grupo'] == fg].copy()
            for (id_sig, item_code), df_group in df_sheet.groupby(['ID_SIG', 'ItemCode'], sort=False):
                total_monto  = df_group['Monto_A_Ingresar'].sum()
                if pd.isna(total_monto):
                    total_monto = 0.0
                whs_group    = str(df_group.iloc[0]['WhsCode'])
                costos_grupo = df_group['Costo_SIG'].dropna()
                costo_grupo  = f"{float(costos_grupo.iloc[0]):.4f}" if not costos_grupo.empty else "-"
                desc_grupo   = str(df_group.iloc[0].get('Descripcion', ''))
                try:
                    tienda_fmt = f"P{int(id_sig):04d}"
                except Exception:
                    tienda_fmt = str(id_sig)

                parent_iid = tree.insert("", "end", open=var_expandir_todo.get(),
                                         tags=('total_row',), values=(
                    item_code, desc_grupo, "-", "SUMATORIA TOTAL",
                    f"{total_monto:.4f}", costo_grupo, whs_group, "C0001", tienda_fmt, "-", "-", "-", "-"
                ))

                for _, row in df_group.iterrows():
                    concepto    = str(row['Concepto'])
                    monto       = float(row['Monto_A_Ingresar'])
                    is_prim_row = bool(row.get('Is_Primary', True))
                    if 'NIVELACIÓN' in concepto:
                        tag = 'nivelacion'
                    elif is_prim_row:
                        tag = 'cola_prim'
                    else:
                        tag = 'cola_sec'
                    try:
                        row_tienda_fmt = f"P{int(row['ID_SIG']):04d}"
                    except Exception:
                        row_tienda_fmt = str(row['ID_SIG'])
                    tree.insert(parent_iid, "end", tags=(tag,), values=(
                        row['ItemCode'], str(row.get('Descripcion', '')),
                        row['Fecha'], concepto,
                        f"{monto:.4f}",
                        f"{float(row.get('Costo_SIG', 0.00)):.4f}",
                        row['WhsCode'], "C0001", row_tienda_fmt,
                        f"{float(row['Stock_A_Fecha']):.4f}",
                        f"{float(row.get('Stock_SIG', 0.00)):.4f}",
                        f"{float(row.get('Movimiento', 0.00)):.4f}",
                        row.get('ID_Movimiento', 'N/A'),
                    ))

            trees.append(tree)

    construir_tabs(_df_activo())

    # Auto-generar Excel al abrir la ventana
    top.after(300, lambda: exportar_excel(_df_activo, soc_sel))

    # ── Botones de acción (btn_frame ya fue empaquetado arriba con side="bottom") ─
    tb.Button(btn_frame, text="🔍 Diagnóstico de Artículos", bootstyle="warning",
              command=lambda: abrir_panel_diagnostico(top, _df_activo(), soc_sel)
              ).pack(side="left", expand=True, fill="x", padx=(0, 6))
    tb.Button(btn_frame, text="📥 Generar Excel de Auditoría", bootstyle="success",
              command=lambda: exportar_excel(_df_activo, soc_sel)
              ).pack(side="left", expand=True, fill="x", padx=(0, 6))

    btn_migrar = tb.Button(btn_frame, text="🗄 Migrar a BD Local", bootstyle="primary")

    def _migrar_una_vez():
        btn_migrar.config(state="disabled", text="🗄 Migración enviada")
        migrar_bd_local(
            df_ajustes, soc_sel, top,
            on_success=lambda: on_migrado(soc_sel) if on_migrado else None,
        )

    btn_migrar.config(command=_migrar_una_vez)
    btn_migrar.pack(side="left", expand=True, fill="x")
