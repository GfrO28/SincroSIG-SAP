import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
import pandas as pd


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

        tb.Label(container,
                 text="Pegue los resultados de cada parte del query SAP. Se acumulan automáticamente.",
                 font=("Segoe UI", 9)).pack(pady=(0, 2), anchor="w")
        tb.Label(container,
                 text="Atajo: Ctrl+V pega directamente · Win+V abre historial del portapapeles",
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
        self.tree.heading("item",  text="Artículo")
        self.tree.heading("whs",   text="Almacén")
        self.tree.heading("stock", text="Stock SAP")
        for c in cols:
            self.tree.column(c, width=260, anchor="center")

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
            rename_map = {
                'Número de artículo': 'ItemCode',
                'Código de almacén':  'WhsCode',
                'Stock_A_Fecha':      'Stock_A_Fecha',
            }
            df_nueva = df_nueva.rename(columns=rename_map)

            if 'WhsCode' in df_nueva.columns:
                df_nueva['WhsCode'] = df_nueva['WhsCode'].astype(str).str.strip().str.zfill(2)
            if 'Stock_A_Fecha' in df_nueva.columns:
                df_nueva['Stock_A_Fecha'] = (df_nueva['Stock_A_Fecha']
                                              .astype(str).str.replace(',', '').astype(float))

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
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.lbl_estado.config(text="Sin datos cargados.")
        self.btn_confirmar.config(state="disabled")

    def _refrescar_vista(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for _, row in self.df_data.iterrows():
            self.tree.insert("", "end", values=(
                row.get('ItemCode', 'N/A'),
                row.get('WhsCode',  'N/A'),
                f"{float(row.get('Stock_A_Fecha', 0)):.4f}",
            ))
        n = len(self.df_data)
        self.lbl_estado.config(
            text=f"{n} artículo(s) acumulados  ·  {self._partes} parte(s) pegada(s)."
        )
        self.btn_confirmar.config(state="normal" if n > 0 else "disabled")

    def confirmar(self):
        self.callback_confirmar(self.df_data)
