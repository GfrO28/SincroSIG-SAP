import os
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import threading
import json
import pandas as pd
import pyperclip
import ttkbootstrap as tb
from datetime import datetime, timedelta, date as _date
import calendar as _cal
from config.db import get_connections
from gui.progress_window import ProgressWindow

# ==========================================
# 🗺️ MAPEO DE TIENDAS: SIG (ID) -> SAP (WhsCode)
# ==========================================
MAPEO_TIENDAS_SAP = {
    "37": "02", "45": "03", "84": "04", "87": "05", "46": "06", 
    "92": "07", "53": "08", "12": "09", "83": "10", "105": "11",
    "03": "12", "05": "13", "09": "14", "14": "15", "22": "16",
    "24": "17", "25": "18", "26": "19", "27": "20", "30": "21",
    "31": "22", "34": "23", "35": "24", "36": "25", "41": "26",
    "42": "27", "43": "28", "47": "29", "48": "30", "49": "31",
    "50": "32", "52": "33", "54": "34", "55": "35", "58": "36",
    "59": "37", "60": "38", "61": "39", "62": "40", "63": "41",
    "64": "42", "65": "43", "66": "44", "67": "45", "69": "46",
    "71": "47", "72": "48", "73": "49", "74": "50", "76": "51",
    "80": "52", "81": "53", "82": "54", "85": "55", "86": "56",
    "88": "57", "89": "58", "90": "59", "91": "60", "93": "61",
    "94": "62", "95": "63", "96": "64", "97": "65", "104": "66",
    "106": "67"
}

# ==========================================
# 📅 SELECTOR DE FECHA CON MINI CALENDARIO
# ==========================================
class _CalendarioPopup(tk.Toplevel):
    _MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
              "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    _DIAS  = ["Do","Lu","Ma","Mi","Ju","Vi","Sá"]

    def __init__(self, anchor, callback, fecha_ini=None):
        super().__init__(anchor.winfo_toplevel())
        self.overrideredirect(True)
        self.resizable(False, False)
        self.callback   = callback
        self._parent_tl = anchor.winfo_toplevel()
        d = fecha_ini or datetime.now().date()
        self._anio, self._mes = d.year, d.month
        self._construir()
        self.update_idletasks()
        ax = anchor.winfo_rootx()
        ay = anchor.winfo_rooty() + anchor.winfo_height() + 2
        pw = self.winfo_reqwidth()
        if ax + pw > self.winfo_screenwidth():
            ax = self.winfo_screenwidth() - pw
        self.geometry(f"+{ax}+{ay}")
        self.bind('<Escape>', lambda _: self.destroy())
        self._bid = self._parent_tl.bind('<Button-1>', self._clic_externo, '+')

    def destroy(self):
        try:
            self._parent_tl.unbind('<Button-1>', self._bid)
        except Exception:
            pass
        if self.winfo_exists():
            super().destroy()

    def _clic_externo(self, event):
        if not self.winfo_exists():
            return
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = self.winfo_width(), self.winfo_height()
        if not (px <= event.x_root <= px + pw and py <= event.y_root <= py + ph):
            self.destroy()

    def _construir(self):
        outer = tk.Frame(self, bg="#2c3e50", bd=1, relief="solid")
        outer.pack(fill="both", expand=True)
        hdr = tk.Frame(outer, bg="#2c3e50")
        hdr.pack(fill="x", padx=4, pady=4)
        tk.Button(hdr, text="◀", bg="#2c3e50", fg="white", relief="flat",
                  activebackground="#34495e", font=("Segoe UI", 9, "bold"),
                  command=self._mes_ant, cursor="hand2").pack(side="left")
        self._lbl = tk.Label(hdr, text="", bg="#2c3e50", fg="white",
                             font=("Segoe UI", 9, "bold"), width=16)
        self._lbl.pack(side="left", expand=True)
        tk.Button(hdr, text="▶", bg="#2c3e50", fg="white", relief="flat",
                  activebackground="#34495e", font=("Segoe UI", 9, "bold"),
                  command=self._mes_sig, cursor="hand2").pack(side="right")
        dias_hdr = tk.Frame(outer, bg="#ecf0f1")
        dias_hdr.pack(fill="x", padx=4)
        for d in self._DIAS:
            tk.Label(dias_hdr, text=d, width=3, bg="#ecf0f1", fg="#7f8c8d",
                     font=("Segoe UI", 8, "bold")).pack(side="left")
        self._grid = tk.Frame(outer, bg="white")
        self._grid.pack(padx=4, pady=(2, 4))
        self._renderizar()

    def _renderizar(self):
        for w in self._grid.winfo_children():
            w.destroy()
        self._lbl.config(text=f"{self._MESES[self._mes - 1]}  {self._anio}")
        hoy = datetime.now().date()
        for semana in _cal.Calendar(firstweekday=6).monthdayscalendar(self._anio, self._mes):
            fila = tk.Frame(self._grid, bg="white")
            fila.pack()
            for dia in semana:
                if dia == 0:
                    tk.Label(fila, text="", width=3, bg="white").pack(side="left", padx=1, pady=1)
                else:
                    es_hoy = (dia == hoy.day and self._mes == hoy.month and self._anio == hoy.year)
                    tk.Button(fila, text=str(dia), width=3, relief="flat", cursor="hand2",
                              bg="#2c3e50" if es_hoy else "white",
                              fg="white"   if es_hoy else "#2c3e50",
                              activebackground="#bdc3c7", font=("Segoe UI", 9),
                              command=lambda d=dia: self._seleccionar(d)
                              ).pack(side="left", padx=1, pady=1)

    def _mes_ant(self):
        self._mes, self._anio = (12, self._anio - 1) if self._mes == 1 else (self._mes - 1, self._anio)
        self._renderizar()

    def _mes_sig(self):
        self._mes, self._anio = (1, self._anio + 1) if self._mes == 12 else (self._mes + 1, self._anio)
        self._renderizar()

    def _seleccionar(self, dia):
        self.callback(_date(self._anio, self._mes, dia))
        self.destroy()


class _CampoFecha(tb.Frame):
    """Entry de fecha con botón que abre mini calendario."""

    def __init__(self, master, **kw):
        ini   = kw.pop('initialdate', None)
        width = kw.pop('width', 11)
        super().__init__(master, **kw)
        self._var = tk.StringVar()
        self._ent = tb.Entry(self, textvariable=self._var, width=width, font=("Segoe UI", 9))
        self._ent.pack(side="left")
        tk.Button(self, text="📅", relief="flat", cursor="hand2",
                  font=("Segoe UI", 9), command=self._abrir).pack(side="left", padx=(1, 0))
        if ini:
            self.set_date(ini)

    def set_date(self, d):
        self._var.set(d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d))

    def get(self):
        return self._var.get()

    def _abrir(self):
        try:
            d = datetime.strptime(self._var.get(), '%Y-%m-%d').date()
        except Exception:
            d = datetime.now().date()
        _CalendarioPopup(self._ent, self.set_date, d)


# ==========================================
# 📊 VENTANA DE RESULTADOS (DISEÑO TIPO EXCEL)
# ==========================================
def mostrar_ventana_resultados(parent, df_ajustes, soc_sel, n_logs_bd=0):
    top = tb.Toplevel(parent)
    top.title(f"Panel de Ajustes Directo SAP - {soc_sel}")
    top.geometry("1450x750")

    def on_closing():
        nonlocal df_ajustes
        df_ajustes = None  # libera el DataFrame antes de destruir la ventana
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", on_closing)

    # Contenedor principal
    main_frame = tb.Frame(top, padding=10)
    main_frame.pack(fill="both", expand=True)

    # Header: título + filtro
    header_frame = tb.Frame(main_frame)
    header_frame.pack(fill="x", pady=(0, 4))
    tb.Label(header_frame, text="Resumen de Reconciliación por Fechas",
             font=("Segoe UI", 12, "bold"), bootstyle="primary").pack(side="left")

    var_ocultar_sin_ingreso = tk.BooleanVar(value=False)
    var_ocultar_stock_ok    = tk.BooleanVar(value=False)
    tb.Checkbutton(header_frame, text="Ocultar artículos con ingreso total = 0",
                   variable=var_ocultar_sin_ingreso, bootstyle="secondary",
                   command=lambda: construir_tabs(_df_activo())).pack(side="right", padx=6)
    tb.Checkbutton(header_frame, text="Ocultar artículos con stock SAP suficiente",
                   variable=var_ocultar_stock_ok, bootstyle="secondary",
                   command=lambda: construir_tabs(_df_activo())).pack(side="right", padx=2)

    # ── Panel de auditoría ───────────────────────────────────────────────
    _cola_df  = df_ajustes[df_ajustes['Concepto'].str.contains('COLA', na=False)]
    _niv_df   = df_ajustes[df_ajustes['Concepto'].str.contains('NIVELACIÓN', na=False)]
    _prim_df  = _cola_df[_cola_df['Is_Primary'].eq(True)]
    _sec_df   = _cola_df[_cola_df['Is_Primary'].eq(False)]
    _n_prim   = len(_prim_df)
    _n_sec    = len(_sec_df)
    _n_art_n  = _niv_df['ItemCode'].nunique()

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

    # Notebook
    notebook = tb.Notebook(main_frame, bootstyle="info")
    notebook.pack(fill="both", expand=True, pady=5)

    cols    = ("item",     "fecha",      "concepto", "ajuste",           "costo_sig",        "whs",     "id_sig",  "stock_sap",  "stock_sig",  "mov",          "id_mov")
    headers = ["Artículo", "Fecha Reg.", "Concepto", "Cant. a Ingresar", "Precio Unit. SIG", "Almacén", "Tienda",  "Stock SAP",  "Stock SIG",  "Cant. Salida", "ID Mov"]
    widths  = [140,        100,          215,        120,                110,                75,        70,        110,          110,          100,            95]

    style = ttk.Style()
    style.configure("Treeview", rowheight=25)
    for _tab_style in ("TNotebook.Tab", "info.TNotebook.Tab"):
        style.map(_tab_style, foreground=[("selected", "#FFFFFF"), ("!selected", "#1a1a1a")])

    def _df_activo():
        df = df_ajustes.copy()

        if var_ocultar_sin_ingreso.get():
            # Nivel grupo: ocultar grupos cuyo total a ingresar = 0
            # (las filas de COLA individuales dentro de grupos visibles no se tocan)
            totales = df.groupby(['ID_SIG', 'ItemCode'])['Monto_A_Ingresar'].transform('sum')
            df = df[totales > 0]

        if var_ocultar_stock_ok.get():
            # Nivel grupo: ocultar grupos donde la suma de salidas COLA <= Stock SAP
            # (el stock existente ya cubre todas las salidas pendientes)
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

            legend_frame = tb.Frame(tab_frame)
            legend_frame.pack(fill="x", pady=(0, 4))
            for color, texto in [("#F5F0AE", "NIVELACIÓN"), ("#B5EAD7", "COLA Primaria"), ("#FFD8A8", "COLA Secundaria")]:
                tk.Label(legend_frame, text=f"  {texto}  ", bg=color, fg="black", relief="solid",
                         borderwidth=1, font=("Segoe UI", 8, "bold")).pack(side="left", padx=4)

            tree_container = tb.Frame(tab_frame)
            tree_container.pack(fill="both", expand=True)

            tree = ttk.Treeview(tree_container, columns=cols, show="headings", height=20)
            for col, head, w in zip(cols, headers, widths):
                tree.heading(col, text=head)
                tree.column(col, width=w, anchor="center")

            sb_v = ttk.Scrollbar(tree_container, orient="vertical",  command=tree.yview)
            sb_h = ttk.Scrollbar(tab_frame,      orient="horizontal", command=tree.xview)
            tree.configure(yscroll=sb_v.set, xscroll=sb_h.set)
            tree.pack(fill="both", expand=True, side="left")
            sb_v.pack(fill="y", side="left")
            sb_h.pack(fill="x", side="bottom")

            tree.tag_configure('nivelacion', background="#F3E963", foreground="black", font=('Segoe UI', 9, 'bold'))
            tree.tag_configure('cola_prim',  background="#31F03B",  foreground="black", font=('Segoe UI', 9, 'bold'))
            tree.tag_configure('cola_sec',   background="#F89E31",  foreground="black", font=('Segoe UI', 9, 'bold'))
            tree.tag_configure('total_row',  background="#000000",  foreground="white",  font=('Segoe UI', 12, 'bold'))

            df_sheet = df[df['Fecha_Grupo'] == fg].copy()
            for (id_sig, item_code), df_group in df_sheet.groupby(['ID_SIG', 'ItemCode'], sort=False):
                for _, row in df_group.iterrows():
                    concepto    = str(row['Concepto'])
                    monto       = float(row['Monto_A_Ingresar'])
                    is_prim_row = bool(row.get('Is_Primary', True))
                    if 'NIVELACIÓN' in concepto:
                        tag = 'nivelacion'
                    elif is_prim_row:
                        tag = 'cola_prim'  # verde claro — salida del artículo en message
                    else:
                        tag = 'cola_sec'   # naranja claro — salida de artículo secundario del JSON
                    tree.insert("", "end", tags=(tag,), values=(
                        row['ItemCode'], row['Fecha'], concepto,
                        f"{monto:.4f}",
                        f"{float(row.get('Costo_SIG', 0.00)):.4f}",
                        row['WhsCode'], row['ID_SIG'],
                        f"{float(row['Stock_A_Fecha']):.4f}",
                        f"{float(row.get('Stock_SIG', 0.00)):.4f}",
                        f"{float(row.get('Movimiento', 0.00)):.4f}",
                        row.get('ID_Movimiento', 'N/A'),
                    ))
                total_monto  = df_group['Monto_A_Ingresar'].sum()
                whs_group    = str(df_group.iloc[0]['WhsCode'])
                costos_grupo = df_group['Costo_SIG'].dropna()
                costo_grupo  = f"{float(costos_grupo.iloc[0]):.4f}" if not costos_grupo.empty else "-"
                tree.insert("", "end", tags=('total_row',), values=(
                    f"TOTAL  {item_code}", "-", "SUMATORIA ARTÍCULO",
                    f"{total_monto:.4f}", costo_grupo, whs_group, str(id_sig), "-", "-", "-", "-"
                ))
                tree.insert("", "end", values=tuple([""] * len(cols)))

    construir_tabs(df_ajustes)

    # Botón para exportar (mantenemos la función de registro)
    def exportar_excel_pestañas():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ajustes_{soc_sel[:10].strip()}_{timestamp}.xlsx"
        path = os.path.join("SincroSIG", "logs", "SAP", "ConciliacionesSAP", filename)
        
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
                workbook = writer.book
                total_format     = workbook.add_format({'bold': True, 'bg_color': '#FFFF00', 'border': 1})
                num_format       = workbook.add_format({'num_format': '#,##0.0000', 'border': 1})
                num_total_format = workbook.add_format({'bold': True, 'bg_color': '#FFFF00', 'num_format': '#,##0.0000', 'border': 1})
                header_format    = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})

                for fg in sorted(df_ajustes['Fecha_Grupo'].unique()):
                    sheet_name = str(fg).replace("/", "-")[:31]
                    if not sheet_name or sheet_name == "nan": sheet_name = "Ajuste"
                    df_sheet = df_ajustes[df_ajustes['Fecha_Grupo'] == fg].copy()
                    cols_final = ["ItemCode", "Fecha", "Concepto", "Monto_A_Ingresar", "Costo_SIG", "WhsCode", "ID_SIG", "Stock_A_Fecha", "Stock_SIG", "Movimiento", "ID_Movimiento"]
                    worksheet = workbook.add_worksheet(sheet_name)
                    for col_num, value in enumerate(cols_final):
                        worksheet.write(0, col_num, value, header_format)

                    current_row = 1
                    grouped_excel = df_sheet.groupby(['ID_SIG', 'ItemCode'], sort=False)
                    for (id_sig, item_code), df_group in grouped_excel:
                        for _, data in df_group.iterrows():
                            for col_num, col_name in enumerate(cols_final):
                                val = data.get(col_name, "")
                                if pd.isna(val):
                                    worksheet.write(current_row, col_num, "")
                                elif isinstance(val, (int, float)):
                                    worksheet.write(current_row, col_num, val, num_format)
                                else:
                                    worksheet.write(current_row, col_num, str(val))
                            current_row += 1
                        total_monto = df_group['Monto_A_Ingresar'].sum()
                        if pd.isna(total_monto): total_monto = 0.0
                        whs_group   = str(df_group.iloc[0]['WhsCode'])
                        worksheet.merge_range(current_row, 0, current_row, 5,
                                              f"TOTAL ARTÍCULO: {item_code} - TIENDA: {id_sig}", total_format)
                        worksheet.write(current_row, 6, whs_group, total_format)
                        worksheet.write(current_row, 7, "-", total_format)
                        worksheet.write(current_row, 8, "-", total_format)
                        worksheet.write(current_row, 9, total_monto, num_total_format)
                        worksheet.write(current_row, 10, "-", total_format)
                        current_row += 2
                    worksheet.set_column(0, 10, 18)
            messagebox.showinfo("Éxito", f"Archivo de auditoría guardado:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al exportar: {e}")

    tb.Button(top, text="📥 Generar Excel de Auditoría", bootstyle="success", command=exportar_excel_pestañas).pack(pady=10)

# ==========================================
# 🪟 VENTANA DE PREVISUALIZACIÓN SAP
# ==========================================
class VentanaEntradaSAP(tb.Toplevel):
    def __init__(self, parent, callback_confirmar):
        super().__init__(parent)
        self.title("Previsualización SAP — Acumulador de Partes")
        self.geometry("1000x650")
        self.callback_confirmar = callback_confirmar
        self.df_data = pd.DataFrame()
        self._partes = 0

        container = tb.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        tb.Label(container, text="Pegue los resultados de cada parte del query SAP. Se acumulan automáticamente.",
                 font=("Segoe UI", 9)).pack(pady=(0, 2), anchor="w")
        tb.Label(container, text="Atajo: Ctrl+V pega directamente · Win+V abre historial del portapapeles",
                 font=("Segoe UI", 8), bootstyle="secondary").pack(pady=(0, 6), anchor="w")

        btn_frame = tb.Frame(container)
        btn_frame.pack(fill="x", pady=(0, 4))
        tb.Button(btn_frame, text="📋 Pegar Parte  (Ctrl+V)", bootstyle="info",
                  command=self.pegar_datos).pack(side="left", expand=True, fill="x", padx=(0, 6))
        tb.Button(btn_frame, text="🗑 Limpiar Todo", bootstyle="secondary",
                  command=self.limpiar_datos).pack(side="left")

        self.bind("<Control-v>", lambda _: self.pegar_datos())

        self.lbl_estado = tb.Label(container, text="Sin datos cargados.",
                                   font=("Segoe UI", 9, "italic"), bootstyle="secondary")
        self.lbl_estado.pack(anchor="w", pady=(0, 4))

        cols = ("item", "whs", "stock")
        self.tree = ttk.Treeview(container, columns=cols, show="headings", height=18)
        self.tree.heading("item", text="Artículo")
        self.tree.heading("whs", text="Almacén")
        self.tree.heading("stock", text="Stock SAP")
        for c in cols: self.tree.column(c, width=260, anchor="center")

        sb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        self.tree.pack(fill="both", expand=True, side="left", pady=6)
        sb.pack(fill="y", side="left", pady=6)

        self.btn_confirmar = tb.Button(container, text="🚀 Procesar Cruce", bootstyle="success",
                                       state="disabled", command=self.confirmar)
        self.btn_confirmar.pack(pady=10, fill="x", side="bottom")

    def pegar_datos(self):
        try:
            df_nueva = pd.read_clipboard(sep='\t')
            df_nueva.columns = [c.strip() for c in df_nueva.columns]
            rename_map = {'Número de artículo': 'ItemCode', 'Código de almacén': 'WhsCode',
                          'Stock_A_Fecha': 'Stock_A_Fecha'}
            df_nueva = df_nueva.rename(columns=rename_map)

            if 'WhsCode' in df_nueva.columns:
                df_nueva['WhsCode'] = df_nueva['WhsCode'].astype(str).str.strip().str.zfill(2)
            if 'Stock_A_Fecha' in df_nueva.columns:
                df_nueva['Stock_A_Fecha'] = df_nueva['Stock_A_Fecha'].astype(str).str.replace(',', '').astype(float)

            if self.df_data.empty:
                self.df_data = df_nueva
            else:
                self.df_data = (pd.concat([self.df_data, df_nueva], ignore_index=True)
                                  .drop_duplicates(subset=['ItemCode', 'WhsCode'], keep='last'))

            self._partes += 1
            self._refrescar_vista()
        except Exception as e:
            messagebox.showerror("Error", f"Error al leer datos: {e}")

    def limpiar_datos(self):
        self.df_data = pd.DataFrame()
        self._partes = 0
        for i in self.tree.get_children(): self.tree.delete(i)
        self.lbl_estado.config(text="Sin datos cargados.")
        self.btn_confirmar.config(state="disabled")

    def _refrescar_vista(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for _, row in self.df_data.iterrows():
            self.tree.insert("", "end", values=(
                row.get('ItemCode', 'N/A'), row.get('WhsCode', 'N/A'),
                f"{float(row.get('Stock_A_Fecha', 0)):.4f}"
            ))
        n = len(self.df_data)
        self.lbl_estado.config(
            text=f"{n} artículo(s) acumulados  ·  {self._partes} parte(s) pegada(s)."
        )
        self.btn_confirmar.config(state="normal" if n > 0 else "disabled")

    def confirmar(self):
        self.callback_confirmar(self.df_data)
        # La ventana permanece abierta para poder re-ejecutar sin volver a pegar datos

# ==========================================
# 📝 LOG DE REGISTROS CON MESSAGE NO RECONOCIDO
# ==========================================
def _escribir_log_parseo(soc_sel, registros):
    folder = os.path.join("SincroSIG", "logs", "SAP", "logs_errorparseo")
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre = f"{soc_sel[:20].strip().replace(' ', '_')}_ERRORPARSEO_{timestamp}.txt"
    path = os.path.join(folder, nombre)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"REGISTROS OMITIDOS — MESSAGE NO RECONOCIDO\n")
        f.write(f"Sociedad : {soc_sel}\n")
        f.write(f"Generado : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total    : {len(registros)} registro(s)\n")
        f.write("=" * 65 + "\n\n")
        for i, r in enumerate(registros, 1):
            f.write(f"[{i}]\n")
            f.write(f"  Fecha         : {r['fecha']}\n")
            f.write(f"  Creado        : {r.get('created_at', '?')}\n")
            f.write(f"  Tienda (ID)   : {r['idtienda']}\n")
            f.write(f"  ID Movimiento : {r['idmovimiento']}\n")
            f.write(f"  Message       : {r['message']}\n")
            dl = r.get('document_lines', [])
            f.write(f"  DocumentLines : {len(dl)} línea(s)\n")
            for d in dl:
                f.write(f"    {d}\n")
            f.write("\n")
    return nombre, path

# ==========================================
# ⚙️ INTERFAZ PRINCIPAL
# ==========================================
def abrir_interfaz_reconciliacion(root):
    win = tb.Toplevel(root)
    win.title("Reconciliación de Stock SAP")
    win.geometry("700x500")
    sociedades_dict = {}

    def cargar_sociedades():
        try:
            conn_sig, cur_sig, _, _ = get_connections() 
            cur_sig.execute("""SELECT e.idempresas, e.rs1, e.ruc FROM empresas e 
                               LEFT JOIN tienda t ON t.idempresas = e.idempresas AND t.activo=1
                               WHERE t.nomb_abrev<>'' AND e.idempresas NOT IN (59,124)
                               GROUP BY e.idempresas ORDER BY e.idempresas*1;""")
            res = cur_sig.fetchall()
            win.after(0, lambda: configurar_ui(res))
        except Exception as e:
            win.after(0, lambda m=str(e): messagebox.showerror("Error", m))

    def obtener_lista_tiendas(id_empresa):
        conn_sig, cur_sig, _, _ = get_connections()
        cur_sig.execute("SELECT idtienda FROM tienda WHERE idempresas = %s AND activo = 1", (id_empresa,))
        return ",".join([str(r['idtienda']) for r in cur_sig.fetchall()])

    def configurar_ui(sociedades):
        container = tb.Frame(win, padding=20) 
        container.pack(fill="both", expand=True)
        tb.Label(container, text="1. Seleccione Sociedad:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        cbo_sociedad = tb.Combobox(container, state="readonly", width=70)
        cbo_sociedad['values'] = [s['rs1'] for s in sociedades]
        cbo_sociedad.pack(pady=5)
        nonlocal sociedades_dict
        sociedades_dict = {s['rs1']: s['idempresas'] for s in sociedades}

        frame_fechas = tb.LabelFrame(container, text=" 2. Rango de Fechas ")
        frame_fechas.pack(fill="x", pady=15, padx=10)

        _hoy        = datetime.now().date()
        _ayer       = _hoy - timedelta(days=1)
        _primer_dia = _hoy.replace(day=1)

        tb.Label(frame_fechas, text="Desde:", font=("Segoe UI", 9)).grid(row=0, column=0, padx=(10, 2), pady=10)
        ent_desde = _CampoFecha(frame_fechas, initialdate=_primer_dia)
        ent_desde.grid(row=0, column=1, padx=5, pady=10)

        tb.Label(frame_fechas, text="Hasta:", font=("Segoe UI", 9)).grid(row=0, column=2, padx=(15, 2))
        ent_hasta = _CampoFecha(frame_fechas, initialdate=_ayer)
        ent_hasta.grid(row=0, column=3, padx=5)

        var_secundarios = tk.BooleanVar(value=False)

        def func_generar_query():
            soc_sel = cbo_sociedad.get()
            if not soc_sel: return
            id_emp = sociedades_dict[soc_sel]
            incluir_sec = var_secundarios.get()
            label_modo = "Primarios + Secundarios" if incluir_sec else "Solo Primarios"
            progress = ProgressWindow(win, f"Generando Query SAP ({label_modo})...")
            def tarea():
                try:
                    conn_sig, cur_sig, _, _ = get_connections()
                    tiendas_csv = obtener_lista_tiendas(id_emp)
                    cur_sig.execute(f"SELECT idtienda, fecha, json, message, idmovimiento, created_at FROM log_transfer_sunsap WHERE fecha BETWEEN %s AND %s AND registered=0 AND nomtabla LIKE %s AND idtienda IN ({tiendas_csv})", (ent_desde.get(), ent_hasta.get(), "%salidas%"))
                    logs_raw_q = cur_sig.fetchall()

                    # Deduplicar por idmovimiento: conservar el de mayor created_at
                    seen_q = {}
                    for l in logs_raw_q:
                        mid = l['idmovimiento']
                        if mid not in seen_q or l['created_at'] > seen_q[mid]['created_at']:
                            seen_q[mid] = l
                    logs = list(seen_q.values())

                    primary_set = set()
                    secondary_set = set()
                    errores_parseo_q = []
                    for l in logs:
                        try:
                            js = json.loads(l['json'])
                            id_str = str(l['idtienda']).zfill(2)
                            whs = MAPEO_TIENDAS_SAP.get(id_str)
                            if whs:
                                try:
                                    start = int(l['message'].split('line: ')[1].split(']')[0]) - 1
                                except:
                                    errores_parseo_q.append({
                                        'fecha': l.get('fecha', '?'),
                                        'idtienda': l.get('idtienda', '?'),
                                        'idmovimiento': l.get('idmovimiento', '?'),
                                        'created_at': l.get('created_at', '?'),
                                        'message': l.get('message', ''),
                                        'document_lines': [
                                            f"#{j+1:>3}  ItemCode: {dl.get('ItemCode','?'):<20}  Qty: {dl.get('Quantity','?')}"
                                            for j, dl in enumerate(js.get('DocumentLines', []))
                                        ]
                                    })
                                    continue
                                for i, line in enumerate(js.get('DocumentLines', [])):
                                    key = (line['ItemCode'], whs)
                                    if i == start:
                                        primary_set.add(key)
                                    else:
                                        secondary_set.add(key)  # incluye pre-primarios
                        except: continue

                    if errores_parseo_q:
                        nombre_log, _ = _escribir_log_parseo(soc_sel, errores_parseo_q)

                    items_set = primary_set | secondary_set if incluir_sec else primary_set
                    if not items_set:
                        aviso = (f"\n\n⚠ {len(errores_parseo_q)} registro(s) omitidos por message no reconocido."
                                 f"\nLog: {nombre_log}" if errores_parseo_q else "")
                        return win.after(0, lambda a=aviso: messagebox.showinfo("Info", f"No se encontraron ítems procesables.{a}"))

                    CHAR_LIMIT = 30000
                    q_header = ("SELECT T0.\"ItemCode\",T0.\"Warehouse\" \"WhsCode\","
                                "CAST(SUM(T0.\"InQty\"-T0.\"OutQty\") AS DECIMAL(19,4)) \"Stock_A_Fecha\" "
                                "FROM OINM T0 WHERE ")
                    q_footer = " GROUP BY T0.\"ItemCode\",T0.\"Warehouse\""
                    overhead = len(q_header) + len(q_footer)

                    conditions = [
                        f"(T0.\"ItemCode\"='{item}' AND T0.\"Warehouse\"='{whs}')"
                        for item, whs in items_set
                    ]

                    batches, current, current_len = [], [], overhead
                    for cond in conditions:
                        extra = len(cond) + (4 if current else 0)
                        if current and current_len + extra > CHAR_LIMIT:
                            batches.append(current)
                            current, current_len = [cond], overhead + len(cond)
                        else:
                            current.append(cond)
                            current_len += extra
                    if current:
                        batches.append(current)

                    queries = [q_header + " OR ".join(b) + q_footer for b in batches]

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    tag = "prim_sec" if incluir_sec else "prim"
                    folder = os.path.join("SincroSIG", "logs", "SAP"); os.makedirs(folder, exist_ok=True)
                    for i, q in enumerate(queries, 1):
                        suffix = f"_parte{i}" if len(queries) > 1 else ""
                        path = os.path.join(folder, f"query_{tag}_{soc_sel[:10].strip()}_{timestamp}{suffix}.txt")
                        with open(path, "w", encoding="utf-8") as fout: fout.write(q)

                    pyperclip.copy(queries[0])
                    n_items, n_partes = len(conditions), len(queries)
                    aviso_q = (f"\n\n⚠ {len(errores_parseo_q)} registro(s) omitidos por message no reconocido.\nLog: {nombre_log}"
                               if errores_parseo_q else "")
                    if n_partes == 1:
                        msg = f"[{label_modo}] Query copiado al portapapeles.\n{n_items} artículo(s) únicos.\nGuardado en: {folder}{aviso_q}"
                    else:
                        msg = (f"[{label_modo}] Query dividido en {n_partes} partes (límite {CHAR_LIMIT} chars).\n"
                               f"{n_items} artículos únicos en total.\n"
                               f"Parte 1/{n_partes} copiada al portapapeles.\n"
                               f"Ejecute cada parte en SAP por separado.\nArchivos en: {folder}{aviso_q}")
                    win.after(0, lambda m=msg: messagebox.showinfo("Éxito", m))
                except Exception as e:
                    win.after(0, lambda m=str(e): messagebox.showerror("Error", m))
                finally: progress.close()
            threading.Thread(target=tarea, daemon=True).start()

        _ref_entrada = [None]

        def lanzar_cruce():
            soc = cbo_sociedad.get()
            if not soc: return
            if _ref_entrada[0] is not None and _ref_entrada[0].winfo_exists():
                _ref_entrada[0].lift()
                _ref_entrada[0].focus_force()
                return
            ventana = VentanaEntradaSAP(win, lambda df: ejecutar_reconciliacion(df, soc))
            _ref_entrada[0] = ventana

        def ejecutar_reconciliacion(df_sap, soc_sel):
            progress = ProgressWindow(win, "Realizando Auditoría...")
            def tarea():
                try:
                    conn_sig, cur_sig, _, _ = get_connections()
                    id_emp = sociedades_dict[soc_sel]
                    tiendas_ids = obtener_lista_tiendas(id_emp)
                    f_desde = ent_desde.get()
                    f_hasta = ent_hasta.get()
                    cur_sig.execute(f"SELECT idtienda, fecha, json, message, idmovimiento, created_at FROM log_transfer_sunsap WHERE fecha BETWEEN %s AND %s AND registered=0 AND nomtabla LIKE %s AND idtienda IN ({tiendas_ids})", (f_desde, f_hasta, "%salidas%"))
                    logs_raw = cur_sig.fetchall()

                    # Deduplicar por idmovimiento: conservar el de mayor created_at
                    seen_c = {}
                    for l in logs_raw:
                        mid = l['idmovimiento']
                        if mid not in seen_c or l['created_at'] > seen_c[mid]['created_at']:
                            seen_c[mid] = l
                    logs_raw = list(seen_c.values())

                    incluir_sec = var_secundarios.get()

                    # Pre-pase: recolectar todos los (ItemCode, WhsCode) que son primarios
                    # en algún registro. Sirve para incluir ocurrencias secundarias de esos
                    # ítems en otros registros (salidas fallidas adicionales del mismo ítem).
                    primary_items_global = set()
                    for _l in logs_raw:
                        try:
                            _js  = json.loads(_l['json'])
                            _whs = MAPEO_TIENDAS_SAP.get(str(_l['idtienda']).zfill(2))
                            if not _whs:
                                continue
                            _pidx = int(_l['message'].split('line: ')[1].split(']')[0]) - 1
                            _lines = _js.get('DocumentLines', [])
                            if _pidx < len(_lines):
                                primary_items_global.add((_lines[_pidx]['ItemCode'], _whs))
                        except Exception:
                            pass

                    logs_procesados = []
                    errores_parseo_c = []
                    for l in logs_raw:
                        try:
                            js = json.loads(l['json'])
                            id_str = str(l['idtienda']).zfill(2)
                            whs_sap = MAPEO_TIENDAS_SAP.get(id_str)
                            if whs_sap:
                                try:
                                    primary_idx = int(l['message'].split('line: ')[1].split(']')[0]) - 1
                                except:
                                    errores_parseo_c.append({
                                        'fecha': l.get('fecha', '?'),
                                        'idtienda': l.get('idtienda', '?'),
                                        'idmovimiento': l.get('idmovimiento', '?'),
                                        'created_at': l.get('created_at', '?'),
                                        'message': l.get('message', ''),
                                        'document_lines': [
                                            f"#{j+1:>3}  ItemCode: {dl.get('ItemCode','?'):<20}  Qty: {dl.get('Quantity','?')}"
                                            for j, dl in enumerate(js.get('DocumentLines', []))
                                        ]
                                    })
                                    continue
                                lines = js.get('DocumentLines', [])
                                for i, line in enumerate(lines):
                                    is_primary = (i == primary_idx)
                                    if not is_primary and not incluir_sec:
                                        if i > primary_idx:
                                            # Post-primario: incluir solo si también es primario en otro registro
                                            if (line['ItemCode'], whs_sap) not in primary_items_global:
                                                continue
                                        # Pre-primario (i < primary_idx): siempre incluir,
                                        # forma parte del mismo documento fallido
                                    logs_procesados.append({
                                        'whs': whs_sap,
                                        'id_sig': int(l['idtienda']),
                                        'id_mov': l['idmovimiento'],
                                        'fecha': l['fecha'],
                                        'item': line['ItemCode'],
                                        'qty': float(line['Quantity']),
                                        'is_primary': is_primary
                                    })
                        except: continue
                    df_logs = pd.DataFrame(logs_procesados)
                    if errores_parseo_c:
                        nombre_log_c, _ = _escribir_log_parseo(soc_sel, errores_parseo_c)
                        win.after(0, lambda n=len(errores_parseo_c), nl=nombre_log_c: messagebox.showwarning(
                            "Registros omitidos",
                            f"{n} registro(s) omitidos por message no reconocido.\n"
                            f"Log guardado en:\nlogs/SAP/logs_errorparseo/{nl}"
                        ))
                    items_list = ",".join([f"'{i}'" for i in df_logs['item'].unique()]) if not df_logs.empty else "''"
                    
                    cur_sig.execute(f"SELECT fproceso, saldoinicial, ingresos, salidas, costoprom, idproductos as ItemCode, idtienda FROM saldos WHERE idtienda IN ({tiendas_ids}) AND idproductos IN ({items_list})")
                    df_saldos_raw = pd.DataFrame(cur_sig.fetchall())
                    df_saldos_raw['WhsCode'] = df_saldos_raw['idtienda'].astype(str).str.zfill(2).map(MAPEO_TIENDAS_SAP)
                    df_saldos = df_saldos_raw.sort_values('fproceso', ascending=False).drop_duplicates(['ItemCode', 'idtienda'])

                    # Ítems del log que no figuran en el paste SAP → stock = 0
                    # (el usuario no ejecutó ese batch o el ítem no tiene movimientos en OINM)
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

                    from modules.reconciliacion_sap_service import calcular_ajustes_tres_vias
                    df_final = calcular_ajustes_tres_vias(df_sap_cruce, df_logs, df_saldos)

                    if not df_final.empty:
                        df_costos = df_saldos[['ItemCode', 'idtienda', 'costoprom']].rename(columns={'idtienda': 'ID_SIG', 'costoprom': 'Costo_SIG'})
                        df_final = df_final.merge(df_costos, on=['ItemCode', 'ID_SIG'], how='left')
                        df_final['Fecha'] = df_final['Fecha'].fillna("S/F")
                        df_final['Fecha_Grupo'] = df_final.groupby(['ID_SIG', 'ItemCode'])['Fecha'].transform(lambda x: x.iloc[0] if x.iloc[0] != "SIN FECHA" else "Ajuste")
                        df_final = df_final.sort_values(by=['Fecha_Grupo', 'ID_SIG', 'ItemCode', 'Prioridad', 'Fecha'])

                    n_logs_bd = len(logs_raw)
                    if df_final.empty: win.after(0, lambda: messagebox.showinfo("Info", "Sin diferencias."))
                    else: win.after(0, lambda f=df_final, n=n_logs_bd: mostrar_ventana_resultados(win, f, soc_sel, n))
                except Exception as e:
                    win.after(0, lambda m=str(e): messagebox.showerror("Error", m))
                finally: progress.close()
            threading.Thread(target=tarea, daemon=True).start()

        frame_queries = tb.Frame(container)
        frame_queries.pack(fill="x", pady=(8, 2))
        tb.Button(frame_queries, text="1. Generar Query SAP",
                  command=func_generar_query,
                  bootstyle="info").pack(side="left", expand=True, fill="x", padx=(0, 6))
        tb.Checkbutton(frame_queries, text="Incluir secundarios",
                       variable=var_secundarios, bootstyle="info").pack(side="left")
        tb.Button(container, text="2. Cargar SAP y Cruzar",
                  command=lanzar_cruce, bootstyle="success").pack(fill="x", pady=(2, 0))

    threading.Thread(target=cargar_sociedades, daemon=True).start()