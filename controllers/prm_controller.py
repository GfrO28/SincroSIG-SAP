# controllers/prm_controller.py
"""
Controlador del módulo PRM (Gestión de Diferencias por Categoría).
Ventana única maximizada: menú lateral + panel de contenido que cambia
según el submódulo seleccionado (sin ventanas emergentes por módulo).
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
import threading
import ttkbootstrap as tb
from version import __version__


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades compartidas: estilo oscuro, animación de carga
# ─────────────────────────────────────────────────────────────────────────────

def _prm_dark_style() -> str:
    """
    Registra (una sola vez) el estilo oscuro para todos los Treeview del módulo PRM.
    NOTA: 'background' se omite intencionalmente del configure() para que los
    tag_configure() por fila funcionen correctamente en ttkbootstrap.
    """
    name = "Prm.Treeview"
    s = ttk.Style()
    s.configure(name,
                fieldbackground="#0D1B2A",
                foreground="#ECEFF1",
                rowheight=23)
    s.configure(f"{name}.Heading",
                background="#1A237E",
                foreground="white",
                font=("Segoe UI", 9, "bold"),
                relief="flat")
    s.map(name,
          background=[("selected", "#1565C0"), ("!selected", "#0D1B2A")],
          foreground=[("selected", "white"),   ("!selected", "#ECEFF1")])
    return name


def _tag_defaults(tree: ttk.Treeview):
    """Agrega los tags de fila comunes a cualquier Treeview con estilo PRM."""
    tree.tag_configure("row_odd",   background="#0F2233", foreground="#ECEFF1")
    tree.tag_configure("row_even",  background="#16304A", foreground="#ECEFF1")
    _RED = dict(background="#C62828", foreground="white",
                font=("Segoe UI", 9, "bold"))
    tree.tag_configure("dif",       **_RED)
    tree.tag_configure("solo_a",    **_RED)
    tree.tag_configure("solo_b",    **_RED)
    tree.tag_configure("dif_row",   **_RED)
    tree.tag_configure("solo_compra", **_RED)
    tree.tag_configure("solo_gasto",  **_RED)
    tree.tag_configure("positivo",  **_RED)
    tree.tag_configure("negativo",  background="#1B5E20", foreground="white",
                       font=("Segoe UI", 9, "bold"))
    tree.tag_configure("total_ok",  background="#1A3A5C", foreground="white",
                       font=("Segoe UI", 9, "bold"))
    tree.tag_configure("total_dif", background="#C62828", foreground="white",
                       font=("Segoe UI", 9, "bold"))


class _Ring:
    """
    Anillo circular animado que simula progreso mientras se carga un archivo.
    Se llena hasta ~80 % durante la carga y completa en verde al terminar.
    """
    _S = 26   # tamaño del canvas (px)
    _W = 3    # grosor del trazo

    def __init__(self, parent: tk.Widget, row: int, col: int,
                 bg: str = "#1A2B3C"):
        self._cv  = tk.Canvas(parent, width=self._S, height=self._S,
                              highlightthickness=0, bg=bg)
        self._cv.grid(row=row, column=col, padx=(4, 0))
        self._fill = 0.0
        self._done = False
        self._job  = None

    def _draw(self, color: str = "#42A5F5"):
        m = self._W + 1
        s = self._S - self._W - 1
        self._cv.delete("all")
        self._cv.create_arc(m, m, s, s, start=0, extent=359.9,
                            outline="#1E3347", width=self._W, style="arc")
        extent = self._fill * 360.0
        if extent > 0.5:
            self._cv.create_arc(m, m, s, s, start=90, extent=-extent,
                                outline=color, width=self._W, style="arc")

    def start(self):
        """Inicia la animación de llenado."""
        self._step()

    def _step(self):
        if self._done:
            return
        target = 0.80
        if self._fill < target:
            self._fill = min(self._fill + target / 80, target)
        self._draw()
        self._job = self._cv.after(20, self._step)

    def stop(self):
        """Completa el anillo en verde y lo destruye tras un destello."""
        self._done = True
        if self._job:
            try:
                self._cv.after_cancel(self._job)
            except Exception:
                pass
        self._fill = 1.0
        try:
            self._draw(color="#66BB6A")
            self._cv.after(650, self._safe_destroy)
        except Exception:
            pass

    def _safe_destroy(self):
        try:
            self._cv.destroy()
        except Exception:
            pass


def _load_async(path: str, read_fn, ring: _Ring, on_done):
    """
    Ejecuta read_fn(path) en un hilo daemon.
    Llama ring.stop() y on_done(df, err) en el hilo principal al terminar.
    """
    def _worker():
        try:
            result = read_fn(path)
            try:
                ring._cv.after(0, lambda: _finish(result, None))
            except Exception:
                pass
        except Exception as exc:
            try:
                ring._cv.after(0, lambda: _finish(None, exc))
            except Exception:
                pass

    def _finish(result, err):
        ring.stop()
        on_done(result, err)

    threading.Thread(target=_worker, daemon=True).start()
    ring.start()


# ─────────────────────────────────────────────────────────────────────────────
# Ventana principal PRM — menú lateral + panel de contenido (ventana única)
# ─────────────────────────────────────────────────────────────────────────────

def abrir_prm(root: tk.Misc) -> None:
    """
    Ventana única del módulo PRM: se abre maximizada, con un menú lateral
    fijo a la izquierda y un panel de contenido a la derecha que ocupa el
    resto del espacio y se reajusta al redimensionar la ventana. Cada
    submódulo se construye una sola vez (perezosamente) y se conserva su
    estado al cambiar de pestaña.
    """
    win = tk.Toplevel(root)
    win.title("PRM – Gestión de Diferencias")
    try:
        win.state("zoomed")
    except tk.TclError:
        win.attributes("-zoomed", True)
    win.minsize(1024, 650)

    win.columnconfigure(0, weight=0)
    win.columnconfigure(1, weight=1)
    win.rowconfigure(0, weight=1)

    _SIDEBAR_BG = "#0A1420"
    sidebar = tk.Frame(win, bg=_SIDEBAR_BG, width=210)
    sidebar.grid(row=0, column=0, sticky="ns")
    sidebar.grid_propagate(False)

    content = tk.Frame(win, bg="#0D1B2A")
    content.grid(row=0, column=1, sticky="nsew")
    content.rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)

    # ── Marca ────────────────────────────────────────────────────────────
    brand = tk.Frame(sidebar, bg=_SIDEBAR_BG)
    brand.pack(fill="x", padx=18, pady=(18, 14))
    tk.Label(brand, text="PRM", font=("Segoe UI", 18, "bold"),
             bg=_SIDEBAR_BG, fg="#42A5F5").pack(anchor="w")
    tk.Label(brand, text="Gestión de Diferencias", font=("Segoe UI", 8),
             bg=_SIDEBAR_BG, fg="#78909C").pack(anchor="w", pady=(2, 0))
    tk.Frame(sidebar, height=1, bg="#16304A").pack(fill="x", padx=18, pady=(0, 8))

    nav_frame = tk.Frame(sidebar, bg=_SIDEBAR_BG)
    nav_frame.pack(fill="both", expand=True, padx=10)

    tk.Frame(sidebar, height=1, bg="#16304A").pack(fill="x", padx=18, pady=(8, 0))
    tk.Label(sidebar, text=f"SincroSIG · v{__version__}", bg=_SIDEBAR_BG, fg="#546E7A",
             font=("Segoe UI", 7)).pack(pady=(8, 14))

    modulos = [
        ("pea",       "👥", "Diferencias PEA",       "#1565C0", _build_pea),
        ("menaje",    "🍽️", "Diferencias Menaje",    "#2E7D32", _build_menaje),
        ("marketing", "📢", "Diferencias Marketing", "#E65100", _build_marketing),
        ("movicaja",  "💰", "Diferencias Movicaja",  "#6A1B9A", _build_movicaja),
        ("compras",   "🛒", "Diferencias Compras",   "#AD1457", _build_compras),
    ]

    nav_widgets = {}
    builders = {}
    for mod_id, icon, label, color, builder in modulos:
        builders[mod_id] = builder
        item = tk.Frame(nav_frame, bg=_SIDEBAR_BG)
        item.pack(fill="x", pady=2)
        stripe = tk.Frame(item, width=3, bg=_SIDEBAR_BG)
        stripe.pack(side="left", fill="y")
        btn = tk.Button(item, text=f"  {icon}  {label}", anchor="w",
                        font=("Segoe UI", 10), bg=_SIDEBAR_BG, fg="#90A4AE",
                        activebackground="#13203A", activeforeground="white",
                        relief="flat", bd=0, padx=6, pady=9, cursor="hand2",
                        command=lambda m=mod_id: _switch_tab(m))
        btn.pack(side="left", fill="both", expand=True)
        nav_widgets[mod_id] = (stripe, btn, color)

    def _set_active(mod_id):
        for mid, (stripe, btn, color) in nav_widgets.items():
            active = (mid == mod_id)
            stripe.config(bg=color if active else _SIDEBAR_BG)
            btn.config(bg="#13203A" if active else _SIDEBAR_BG,
                       fg="white" if active else "#90A4AE",
                       font=("Segoe UI", 10, "bold" if active else "normal"))

    _tab_frames = {}

    def _get_or_build(mod_id):
        if mod_id not in _tab_frames:
            frame = tk.Frame(content, bg="#0D1B2A")
            frame.grid(row=0, column=0, sticky="nsew")
            builders[mod_id](frame)
            _tab_frames[mod_id] = frame
        return _tab_frames[mod_id]

    def _switch_tab(mod_id):
        _get_or_build(mod_id).tkraise()
        _set_active(mod_id)

    _switch_tab("pea")


# ─────────────────────────────────────────────────────────────────────────────
# PEA — panel con DATA PEA (30%) + Facturas/Detalle (70%)
# ─────────────────────────────────────────────────────────────────────────────

def _build_pea(parent: tk.Widget) -> None:
    from modules import prm_pea
    import pandas as pd

    _TREE_STYLE = _prm_dark_style()
    _BG_HDR  = "#1565C0"
    _BG_CTRL = "#1A2B3C"
    _LBL_FONT  = ("Segoe UI", 9, "bold")
    _FILE_FONT = ("Segoe UI", 9)

    # ── Header coloreado ──────────────────────────────────────────────────
    hdr_top = tk.Frame(parent, bg=_BG_HDR)
    hdr_top.pack(fill="x")
    tk.Label(hdr_top, text="👥  Diferencias PEA",
             font=("Segoe UI", 12, "bold"),
             bg=_BG_HDR, fg="white", pady=9).pack(side="left", padx=16)
    tk.Frame(parent, height=2, bg="#0D47A1").pack(fill="x")

    _raw_c   = [None]
    _raw_is  = [None]
    _raw_pea = [None]
    _pivot_tree_ref      = [None]
    _tiendas_todas       = []
    _tienda_fact_difs    = {}
    _cruces_actuales     = [[]]
    _var_filtro_fact_tda = tk.BooleanVar(value=False)
    _var_solo_dif_fact   = tk.BooleanVar(value=False)

    # ── Control bar ───────────────────────────────────────────────────────
    ctrl_wrap = tk.Frame(parent, bg=_BG_CTRL)
    ctrl_wrap.pack(fill="x")
    ctrl = ttk.Frame(ctrl_wrap, padding=(14, 10, 14, 8))
    ctrl.pack(fill="x")
    ctrl.columnconfigure(1, weight=1)

    ttk.Label(ctrl, text="Compras:",   font=_LBL_FONT).grid(row=0, column=0, sticky="w")
    lbl_c   = ttk.Label(ctrl, text="Sin cargar", foreground="gray", font=_FILE_FONT)
    lbl_c.grid(row=0, column=1, sticky="w", padx=10)

    ttk.Label(ctrl, text="I&S:",      font=_LBL_FONT).grid(row=1, column=0, sticky="w", pady=(4, 0))
    lbl_is  = ttk.Label(ctrl, text="Sin cargar", foreground="gray", font=_FILE_FONT)
    lbl_is.grid(row=1, column=1, sticky="w", padx=10, pady=(4, 0))

    ttk.Label(ctrl, text="DATA PEA:", font=_LBL_FONT).grid(row=2, column=0, sticky="w", pady=(4, 0))
    lbl_pea = ttk.Label(ctrl, text="Sin cargar", foreground="gray", font=_FILE_FONT)
    lbl_pea.grid(row=2, column=1, sticky="w", padx=10, pady=(4, 0))

    ttk.Label(ctrl, text="Tienda:",   font=_LBL_FONT).grid(row=3, column=0, sticky="w", pady=(8, 0))
    cmb_tienda = ttk.Combobox(ctrl, state="disabled", width=14, font=_FILE_FONT)
    cmb_tienda.grid(row=3, column=1, sticky="w", padx=10, pady=(8, 0))

    tk.Frame(parent, height=2, bg="#0D47A1").pack(fill="x")

    def _cargar_c():
        path = filedialog.askopenfilename(parent=parent, title="Seleccionar Compras",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")])
        if not path:
            return
        ring = _Ring(ctrl, row=0, col=3, bg=_BG_CTRL)
        lbl_c.config(text="Cargando…", foreground="gray")

        def on_done(df, err):
            if err:
                lbl_c.config(text="Error al cargar", foreground="#C62828")
                messagebox.showerror("Error", str(err), parent=parent)
            else:
                _raw_c[0] = df
                lbl_c.config(text=Path(path).name, foreground="#2E7D32")
                if _raw_is[0] is not None and _raw_pea[0] is not None:
                    _precompute_fact_difs_async()

        _load_async(path, pd.read_excel, ring, on_done)

    def _cargar_is():
        path = filedialog.askopenfilename(parent=parent, title="Seleccionar I&S",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")])
        if not path:
            return
        ring = _Ring(ctrl, row=1, col=3, bg=_BG_CTRL)
        lbl_is.config(text="Cargando…", foreground="gray")

        def on_done(df, err):
            if err:
                lbl_is.config(text="Error al cargar", foreground="#C62828")
                messagebox.showerror("Error", str(err), parent=parent)
            else:
                _raw_is[0] = df
                lbl_is.config(text=Path(path).name, foreground="#2E7D32")
                if _raw_c[0] is not None and _raw_pea[0] is not None:
                    _precompute_fact_difs_async()

        _load_async(path, pd.read_excel, ring, on_done)

    def _cargar_pea():
        path = filedialog.askopenfilename(parent=parent, title="Seleccionar DATA PEA",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")])
        if not path:
            return
        ring = _Ring(ctrl, row=2, col=3, bg=_BG_CTRL)
        lbl_pea.config(text="Cargando…", foreground="gray")

        def on_done(df, err):
            if err:
                lbl_pea.config(text="Error al cargar", foreground="#C62828")
                messagebox.showerror("Error", str(err), parent=parent)
            else:
                _raw_pea[0] = df
                lbl_pea.config(text=Path(path).name, foreground="#2E7D32")
                tiendas = prm_pea.obtener_tiendas_pea(df)
                _tiendas_todas.clear()
                _tiendas_todas.extend(tiendas)
                _aplicar_filtro_tiendas()
                if _raw_c[0] is not None and _raw_is[0] is not None:
                    _precompute_fact_difs_async()

        _load_async(path, pd.read_excel, ring, on_done)

    tb.Button(ctrl, text="Obtener Compras",  command=_cargar_c,
              bootstyle="secondary-outline").grid(row=0, column=2, padx=(0, 4))
    tb.Button(ctrl, text="Obtener I&S",       command=_cargar_is,
              bootstyle="secondary-outline").grid(row=1, column=2, padx=(0, 4), pady=(4, 0))
    tb.Button(ctrl, text="Obtener DATA PEA",  command=_cargar_pea,
              bootstyle="secondary-outline").grid(row=2, column=2, padx=(0, 4), pady=(4, 0))

    def _generar():
        if _raw_c[0]   is None:
            messagebox.showwarning("Atención", "Cargue el archivo de Compras.",  parent=parent); return
        if _raw_is[0]  is None:
            messagebox.showwarning("Atención", "Cargue el archivo de I&S.",      parent=parent); return
        if _raw_pea[0] is None:
            messagebox.showwarning("Atención", "Cargue el archivo de DATA PEA.", parent=parent); return
        tienda = cmb_tienda.get().strip()
        if not tienda:
            messagebox.showwarning("Atención", "Seleccione una tienda.", parent=parent); return
        try:
            df_pivot   = prm_pea.procesar_pivot_pea(_raw_pea[0], tienda)
            _rebuild_pivot(df_pivot)
            df_fact_c  = prm_pea.obtener_facturas_compras(_raw_c[0],  tienda)
            df_fact_is = prm_pea.obtener_facturas_is(_raw_is[0], tienda)
            cruces     = prm_pea.cruzar_por_clave(df_fact_c, df_fact_is)
            _cerrar_detalle()
            _poblar_facturas(cruces)
        except KeyError as e:
            messagebox.showerror("Columna no encontrada",
                f"Columna esperada no encontrada: {e}\n\nVerificá los encabezados del Excel.",
                parent=parent)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=parent)

    def _aplicar_filtro_tiendas():
        """Actualiza el combobox según el checkbox de filtro."""
        if not _tiendas_todas:
            return
        if _var_filtro_fact_tda.get() and _tienda_fact_difs:
            lista = [t for t in _tiendas_todas if _tienda_fact_difs.get(t, False)]
        else:
            lista = list(_tiendas_todas)
        cmb_tienda["values"] = lista
        cmb_tienda["state"]  = "readonly" if lista else "disabled"
        if lista:
            cmb_tienda.current(0)
            if _raw_c[0] is not None and _raw_is[0] is not None:
                _generar()

    def _precompute_fact_difs_async():
        """Calcula en background si cada tienda tiene dif en facturas, luego refresca el combobox."""
        snapshot_c  = _raw_c[0]
        snapshot_is = _raw_is[0]
        tiendas     = list(_tiendas_todas)
        def _run():
            result = {}
            for t in tiendas:
                try:
                    result[t] = prm_pea.tienda_tiene_dif_facturas(snapshot_c, snapshot_is, t)
                except Exception:
                    result[t] = False
            def _apply():
                _tienda_fact_difs.clear()
                _tienda_fact_difs.update(result)
                _aplicar_filtro_tiendas()
            parent.after(0, _apply)
        threading.Thread(target=_run, daemon=True).start()

    tb.Checkbutton(ctrl,
                   text="Solo tiendas con dif en facturas",
                   variable=_var_filtro_fact_tda,
                   command=_aplicar_filtro_tiendas,
                   bootstyle="warning-round-toggle",
                   ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

    # Auto-refresh al cambiar tienda (solo si los 3 archivos están cargados)
    def _on_tienda_change(_e=None):
        _cerrar_detalle()
        if _raw_c[0] is not None and _raw_is[0] is not None and _raw_pea[0] is not None:
            _generar()
    cmb_tienda.bind("<<ComboboxSelected>>", _on_tienda_change)

    # ── Área principal: columna izq. 30% (DATA PEA) / columna der. 70% ─────
    main_area = tk.Frame(parent, bg="#0D1B2A")
    main_area.pack(fill="both", expand=True, padx=10, pady=(6, 10))
    main_area.columnconfigure(0, weight=3)
    main_area.columnconfigure(1, weight=7)
    main_area.rowconfigure(0, weight=1)

    # ── Columna izquierda: pivot DATA PEA (vertical, altura completa) ──────
    pivot_lf = ttk.LabelFrame(main_area, text="DATA PEA – Tabla dinámica (DIF = PEA-GV − COBRO VAN)",
                               padding=(6, 4))
    pivot_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    pivot_container = ttk.Frame(pivot_lf)
    pivot_container.pack(fill="both", expand=True)

    def _fmt_num(v) -> str:
        if v is None:
            return ""
        try:
            n = round(float(v), 2)
            if n != n:
                return ""
            if n == 0:          # evita "-0" por errores de punto flotante
                return "0"
            return f"{n:,.0f}" if n % 1 == 0 else f"{n:,.2f}"
        except (TypeError, ValueError):
            return str(v)

    def _fmt_fecha(v) -> str:
        if hasattr(v, "strftime"):
            return v.strftime("%d/%m/%Y")
        s = str(v).strip()
        return s.split(" ")[0] if " " in s else s

    def _rebuild_pivot(df_pivot: pd.DataFrame):
        for w in pivot_container.winfo_children():
            w.destroy()
        _pivot_tree_ref[0] = None
        if df_pivot is None or df_pivot.empty:
            ttk.Label(pivot_container, text="Sin datos para la tienda seleccionada.",
                      foreground="gray").pack(pady=10)
            return
        cols = list(df_pivot.columns)
        tree = ttk.Treeview(pivot_container, columns=cols, show="headings",
                            height=7, style=_TREE_STYLE)
        for c in cols:
            w_col = 70 if c == "FECHA" else (65 if c == "DIF" else 85)
            tree.heading(c, text=c, anchor="center")
            tree.column(c, width=w_col, anchor="center", stretch=True, minwidth=40)
        _tag_defaults(tree)
        vsb_p = ttk.Scrollbar(pivot_container, orient="vertical",   command=tree.yview)
        hsb_p = ttk.Scrollbar(pivot_container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb_p.set, xscrollcommand=hsb_p.set)
        vsb_p.pack(side="right",  fill="y")
        hsb_p.pack(side="bottom", fill="x")
        tree.pack(fill="both", expand=True)
        total_idx = len(df_pivot) - 1
        for i, (_, row) in enumerate(df_pivot.iterrows()):
            vals = []
            for c in cols:
                vals.append(_fmt_fecha(row[c]) if c == "FECHA" else _fmt_num(row[c]))
            is_total    = (i == total_idx)
            dif_nonzero = False
            if "DIF" in df_pivot.columns:
                try:
                    dv = round(float(row["DIF"]), 2)
                    dif_nonzero = dv != 0      # cualquier diferencia != 0 se resalta
                except (TypeError, ValueError):
                    pass
            if is_total:
                tag = ("total_dif",) if dif_nonzero else ("total_ok",)
            elif dif_nonzero:
                tag = ("dif_row",)
            else:
                tag = ("row_odd",) if i % 2 == 0 else ("row_even",)
            tree.insert("", "end", values=vals, tags=tag)
        _pivot_tree_ref[0] = tree

    # ── Columna derecha: Comparación de Facturas + Detalle inline ──────────
    right_col = tk.Frame(main_area, bg="#0D1B2A")
    right_col.grid(row=0, column=1, sticky="nsew")

    fact_lf = ttk.LabelFrame(
        right_col,
        text="Comparación de Facturas (NRO_DOC CAS)  —  click en fila para ver artículos",
        padding=(6, 4),
    )
    fact_lf.pack(fill="both", expand=True)

    fact_toolbar = tk.Frame(fact_lf)
    fact_toolbar.pack(fill="x")
    tb.Checkbutton(fact_toolbar,
                   text="Solo facturas con diferencia",
                   variable=_var_solo_dif_fact,
                   command=lambda: _poblar_facturas(_cruces_actuales[0]),
                   bootstyle="warning-round-toggle",
                   ).pack(side="right")

    _W_C_DOC = 120; _W_C_TOT = 90; _W_IS_DOC = 120; _W_IS_TOT = 90; _W_DIF = 80

    hdr_frame = tk.Frame(fact_lf)
    hdr_frame.pack(fill="x", padx=2, pady=(2, 0))
    tk.Label(hdr_frame, text="  COMPRAS  ", bg="#1565C0", fg="white",
             font=("Segoe UI", 8, "bold"), pady=3).pack(side="left", fill="x", expand=True)
    tk.Frame(hdr_frame, width=2, bg="#888888").pack(side="left", fill="y")
    tk.Label(hdr_frame, text="  I&S  ", bg="#E65100", fg="white",
             font=("Segoe UI", 8, "bold"), pady=3).pack(side="left", fill="x", expand=True)
    tk.Frame(hdr_frame, width=2, bg="#888888").pack(side="left", fill="y")
    tk.Label(hdr_frame, text="  DIF  ", bg="#37474F", fg="white",
             font=("Segoe UI", 8, "bold"), pady=3, width=8).pack(side="left")

    fact_frame = ttk.Frame(fact_lf)
    fact_frame.pack(fill="both", expand=True, pady=(2, 0))

    fact_cols = ("c_doc", "c_tot", "is_doc", "is_tot", "dif")
    fact_tree = ttk.Treeview(fact_frame, columns=fact_cols, show="headings",
                              selectmode="browse", height=8, style=_TREE_STYLE)
    for _col, _txt, _w in (
        ("c_doc",  "FACTURA", _W_C_DOC),  ("c_tot",  "TOTAL", _W_C_TOT),
        ("is_doc", "FACTURA", _W_IS_DOC), ("is_tot", "TOTAL", _W_IS_TOT),
        ("dif",    "DIF",     _W_DIF),
    ):
        fact_tree.heading(_col, text=_txt, anchor="center")
        fact_tree.column(_col, width=_w, anchor="center", stretch=True)

    _tag_defaults(fact_tree)

    vsb_f = ttk.Scrollbar(fact_frame, orient="vertical", command=fact_tree.yview)
    fact_tree.configure(yscrollcommand=vsb_f.set)
    vsb_f.pack(side="right", fill="y")
    fact_tree.pack(fill="both", expand=True)

    def _fila_tiene_dif(row) -> bool:
        return (row["tipo"] in ("solo_a", "solo_b") or
                (row["dif"] is not None and abs(row["dif"]) > 0.1))

    def _poblar_facturas(cruces: list):
        _cruces_actuales[0] = cruces
        for item in fact_tree.get_children():
            fact_tree.delete(item)
        visible = [r for r in cruces if _fila_tiene_dif(r)] if _var_solo_dif_fact.get() else cruces
        for i, row in enumerate(visible):
            vals = (row["key_a"], _fmt_num(row["val_a"]),
                    row["key_b"], _fmt_num(row["val_b"]),
                    _fmt_num(row["dif"]))
            if row["tipo"] == "match":
                tag = "row_odd" if i % 2 == 0 else "row_even"
            else:
                tag = row["tipo"]
            fact_tree.insert("", "end", values=vals, tags=(tag,))

    # ── Panel de detalle inline (reemplaza la ventana emergente anterior) ──
    detail_frame = tk.Frame(right_col, bg="#122A3D")

    def _cerrar_detalle():
        detail_frame.pack_forget()
        for w in detail_frame.winfo_children():
            w.destroy()

    def _mostrar_detalle_factura(nro_doc: str, tienda: str):
        for w in detail_frame.winfo_children():
            w.destroy()
        try:
            df_art_c   = prm_pea.obtener_articulos_compras(_raw_c[0],  tienda, nro_doc)
            df_art_is  = prm_pea.obtener_articulos_is(_raw_is[0], tienda, nro_doc)
            cruces_art = prm_pea.cruzar_articulos_pea(df_art_c, df_art_is)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=parent)
            return

        hdr = tk.Frame(detail_frame, bg="#122A3D")
        hdr.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(hdr, text=f"Detalle — Factura {nro_doc} · Tienda {tienda}",
                 bg="#122A3D", fg="#90CAF9", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(hdr, text="✕", command=_cerrar_detalle, bg="#122A3D", fg="#90A4AE",
                  bd=0, relief="flat", activebackground="#122A3D", activeforeground="white",
                  cursor="hand2", font=("Segoe UI", 10)).pack(side="right")

        det_tabla = ttk.Frame(detail_frame)
        det_tabla.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("c_cod", "c_art", "c_tot", "is_cod", "is_art", "is_tot", "dif")
        tree_d = ttk.Treeview(det_tabla, columns=cols, show="headings",
                              selectmode="none", style=_TREE_STYLE)
        for _col, _txt, _w in (
            ("c_cod",  "COD_ANTIGUO", 90), ("c_art",  "ARTICULO", 170), ("c_tot",  "TOTAL", 85),
            ("is_cod", "COD_ANTIGUO", 90), ("is_art", "ARTICULO", 170), ("is_tot", "TOTAL", 85),
            ("dif",    "DIF",          80),
        ):
            tree_d.heading(_col, text=_txt, anchor="center")
            tree_d.column(_col, width=_w, anchor="center", stretch=True, minwidth=50)
        _tag_defaults(tree_d)

        vsb_d = ttk.Scrollbar(det_tabla, orient="vertical",   command=tree_d.yview)
        hsb_d = ttk.Scrollbar(det_tabla, orient="horizontal", command=tree_d.xview)
        tree_d.configure(yscrollcommand=vsb_d.set, xscrollcommand=hsb_d.set)
        vsb_d.pack(side="right",  fill="y")
        hsb_d.pack(side="bottom", fill="x")
        tree_d.pack(fill="both", expand=True)

        def _cod(v) -> str:
            s = str(v).strip() if v else ""
            return "" if s in ("", "nan", "None") else s

        for i, row in enumerate(cruces_art):
            vals = (
                _cod(row["c_cod"]),  row.get("c_art", ""), _fmt_num(row["val_a"]),
                _cod(row["is_cod"]), row.get("is_art", ""), _fmt_num(row["val_b"]),
                _fmt_num(row["dif"]),
            )
            if row["tipo"] == "match":
                tag = "row_odd" if i % 2 == 0 else "row_even"
            else:
                tag = row["tipo"]
            tree_d.insert("", "end", values=vals, tags=(tag,))

        detail_frame.pack(fill="both", expand=True, pady=(8, 0))

    def _on_fact_click(_event=None):
        iid = fact_tree.focus()
        if not iid:
            return
        vals   = fact_tree.item(iid, "values")
        nro_doc = vals[0] if vals[0] else vals[2]
        if not nro_doc:
            return
        tienda = cmb_tienda.get().strip()
        if _raw_c[0] is None or _raw_is[0] is None:
            return
        _mostrar_detalle_factura(nro_doc, tienda)

    fact_tree.bind("<<TreeviewSelect>>", _on_fact_click)


# ─────────────────────────────────────────────────────────────────────────────
# Menaje / Marketing — panel genérico resumen por tienda + detalle inline
# ─────────────────────────────────────────────────────────────────────────────

def _build_resumen(parent: tk.Widget, titulo: str, fn_compras, fn_gastos,
                    bg_header: str = "#1565C0") -> None:
    """
    Panel genérico de diferencias por categoría (Menaje, Marketing, …).
    fn_compras / fn_gastos: funciones de filtrado específicas del módulo.
    """
    from modules.prm_menaje import calcular_resumen, cruzar_tienda
    import pandas as pd

    _STYLE   = _prm_dark_style()
    _BG_CTRL = "#1A2B3C"
    _LBL_FT  = ("Segoe UI", 9, "bold")
    _FILE_FT = ("Segoe UI", 9)

    _raw_c: list = [None]
    _raw_g: list = [None]
    _df_c:  list = [None]
    _df_g:  list = [None]
    _resumen_raw = [None]
    _var_filtro_tda = tk.BooleanVar(value=False)

    # ── Header coloreado ──────────────────────────────────────────────────
    hdr_top = tk.Frame(parent, bg=bg_header)
    hdr_top.pack(fill="x")
    tk.Label(hdr_top, text=f"  {titulo}",
             font=("Segoe UI", 12, "bold"),
             bg=bg_header, fg="white", pady=9).pack(side="left", padx=16)
    tk.Frame(parent, height=2, bg="#0D1B2A").pack(fill="x")

    # ── Barra de controles (fondo oscuro) ─────────────────────────────────
    ctrl_wrap = tk.Frame(parent, bg=_BG_CTRL)
    ctrl_wrap.pack(fill="x")
    ctrl = ttk.Frame(ctrl_wrap, padding=(14, 10, 14, 8))
    ctrl.pack(fill="x")
    ctrl.columnconfigure(1, weight=1)

    ttk.Label(ctrl, text="Compras:", font=_LBL_FT).grid(row=0, column=0, sticky="w")
    lbl_c = ttk.Label(ctrl, text="Sin cargar", foreground="gray", font=_FILE_FT)
    lbl_c.grid(row=0, column=1, sticky="w", padx=10)

    def _cargar_compras():
        path = filedialog.askopenfilename(
            parent=parent, title="Seleccionar Compras",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")],
        )
        if not path:
            return
        ring = _Ring(ctrl, row=0, col=3, bg=_BG_CTRL)
        lbl_c.config(text="Cargando…", foreground="gray")

        def on_done(df, err):
            if err:
                lbl_c.config(text="Error al cargar", foreground="#C62828")
                messagebox.showerror("Error", str(err), parent=parent)
            else:
                _raw_c[0] = df
                lbl_c.config(text=Path(path).name, foreground="#2E7D32")

        _load_async(path, pd.read_excel, ring, on_done)

    tb.Button(ctrl, text="Obtener Compras", command=_cargar_compras,
              bootstyle="secondary-outline").grid(row=0, column=2)

    ttk.Label(ctrl, text="Gastos:", font=_LBL_FT).grid(
        row=1, column=0, sticky="w", pady=(6, 0))
    lbl_g = ttk.Label(ctrl, text="Sin cargar", foreground="gray", font=_FILE_FT)
    lbl_g.grid(row=1, column=1, sticky="w", padx=10, pady=(6, 0))

    def _cargar_gastos():
        path = filedialog.askopenfilename(
            parent=parent, title="Seleccionar Gastos",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")],
        )
        if not path:
            return
        ring = _Ring(ctrl, row=1, col=3, bg=_BG_CTRL)
        lbl_g.config(text="Cargando…", foreground="gray")

        def on_done(df, err):
            if err:
                lbl_g.config(text="Error al cargar", foreground="#C62828")
                messagebox.showerror("Error", str(err), parent=parent)
            else:
                _raw_g[0] = df
                lbl_g.config(text=Path(path).name, foreground="#2E7D32")

        _load_async(path, lambda p: pd.read_excel(p, header=1), ring, on_done)

    tb.Button(ctrl, text="Obtener Gastos", command=_cargar_gastos,
              bootstyle="secondary-outline").grid(row=1, column=2, pady=(6, 0))

    def _generar():
        if _raw_c[0] is None:
            messagebox.showwarning("Atención", "Debes cargar el archivo de Compras.", parent=parent)
            return
        if _raw_g[0] is None:
            messagebox.showwarning("Atención", "Debes cargar el archivo de Gastos.", parent=parent)
            return
        try:
            _df_c[0] = fn_compras(_raw_c[0])
            _df_g[0] = fn_gastos(_raw_g[0])
            resumen   = calcular_resumen(_df_c[0], _df_g[0])
            _cerrar_detalle()
            _poblar_tabla(resumen)
        except KeyError as e:
            messagebox.showerror(
                "Columna no encontrada",
                f"Columna esperada no encontrada: {e}\n\n"
                "Verificá que el Excel tenga los encabezados correctos.",
                parent=parent,
            )
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=parent)

    tb.Button(ctrl, text="Generar Cruce", command=_generar,
              bootstyle="success").grid(row=2, column=2, pady=(10, 0))

    def _aplicar_filtro_tda():
        if _resumen_raw[0] is not None:
            _poblar_tabla(_resumen_raw[0])

    tb.Checkbutton(ctrl,
                   text="Solo tiendas con DIF > 0.1",
                   variable=_var_filtro_tda,
                   command=_aplicar_filtro_tda,
                   bootstyle="warning-round-toggle",
                   ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

    tk.Frame(parent, height=2, bg="#0D1B2A").pack(fill="x")

    # ── Hint + tabla resumen + detalle inline ──────────────────────────────
    ttk.Label(parent, text="Haz click en una fila para ver el detalle de registros.",
              font=("Segoe UI", 8), foreground="gray").pack(anchor="w", padx=14, pady=(4, 0))

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    tabla_frame = ttk.Frame(body)
    tabla_frame.pack(fill="both", expand=True)

    cols = ("TDA", "COMPRAS", "GASTOS", "DIF")
    tree = ttk.Treeview(tabla_frame, columns=cols, show="headings",
                        selectmode="browse", height=14, style=_STYLE)

    for c, w in {"TDA": 60, "COMPRAS": 130, "GASTOS": 130, "DIF": 110}.items():
        tree.heading(c, text=c, anchor="center")
        tree.column(c, width=w, anchor="center", stretch=True)

    vsb = ttk.Scrollbar(tabla_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    _tag_defaults(tree)

    def _fmt(v) -> str:
        try:
            n = float(v)
            return f"{n:,.0f}" if n == int(n) else f"{n:,.2f}"
        except (TypeError, ValueError):
            return str(v)

    def _tda_display(v) -> str:
        s = str(v).strip()
        return s[:-2] if s.endswith(".0") else s

    def _poblar_tabla(resumen):
        _resumen_raw[0] = resumen
        for item in tree.get_children():
            tree.delete(item)
        odd = True
        for _, row in resumen.iterrows():
            dif = float(row["DIF"])
            if _var_filtro_tda.get() and abs(dif) <= 0.1:
                continue
            if dif == 0:
                tag = "row_odd" if odd else "row_even"
                odd = not odd
            else:
                tag = "positivo" if dif > 0 else "negativo"
            tree.insert("", "end",
                        values=(_tda_display(row["TDA"]),
                                _fmt(row["COMPRAS"]),
                                _fmt(row["GASTOS"]),
                                _fmt(dif)),
                        tags=(tag,))

    # ── Panel de detalle inline (reemplaza la ventana emergente anterior) ──
    detail_frame = tk.Frame(body, bg="#122A3D")

    def _cerrar_detalle():
        detail_frame.pack_forget()
        for w in detail_frame.winfo_children():
            w.destroy()

    def _v(rec, field) -> str:
        if rec is None:
            return ""
        val = rec.get(field)
        if val is None:
            return ""
        if isinstance(val, float):
            if pd.isna(val):
                return ""
            return f"{val:,.0f}" if val % 1 == 0 else f"{val:,.2f}"
        if hasattr(val, "strftime"):
            return val.strftime("%d/%m/%Y")
        return str(val)

    def _mostrar_detalle(tda: str):
        for w in detail_frame.winfo_children():
            w.destroy()
        rows = cruzar_tienda(_df_c[0], _df_g[0], tda)

        hdr = tk.Frame(detail_frame, bg="#122A3D")
        hdr.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(hdr, text=f"Detalle — Tienda {tda}",
                 bg="#122A3D", fg="#90CAF9", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(hdr, text="✕", command=_cerrar_detalle, bg="#122A3D", fg="#90A4AE",
                  bd=0, relief="flat", activebackground="#122A3D", activeforeground="white",
                  cursor="hand2", font=("Segoe UI", 10)).pack(side="right")

        sub_hdr = tk.Frame(detail_frame, bg="#122A3D")
        sub_hdr.pack(fill="x", padx=10)
        tk.Label(sub_hdr, text="  COMPRAS  ", bg="#1565C0", fg="white",
                 font=("Segoe UI", 9, "bold"), pady=4).pack(side="left", fill="x", expand=True)
        tk.Frame(sub_hdr, width=2, bg="#888888").pack(side="left", fill="y")
        tk.Label(sub_hdr, text="  GASTOS  ", bg="#E65100", fg="white",
                 font=("Segoe UI", 9, "bold"), pady=4).pack(side="left", fill="x", expand=True)

        det_tabla = ttk.Frame(detail_frame)
        det_tabla.pack(fill="both", expand=True, padx=10, pady=(2, 4))

        cols_d = ("c_gr", "c_fec", "c_doc", "c_obs", "c_tot",
                  "sep",
                  "g_gr", "g_fec", "g_doc", "g_obs", "g_tot")
        hdrs = {
            "c_gr":  "GRUPO",   "c_fec": "FECHA", "c_doc": "NRO_DOC",
            "c_obs": "ARTICULO","c_tot": "TOTAL",
            "sep":   "",
            "g_gr":  "TIPO",    "g_fec": "FECHA", "g_doc": "ORDEN",
            "g_obs": "OBSERVACIONES", "g_tot": "TOTAL",
        }
        widths = {
            "c_gr": 80, "c_fec": 80, "c_doc": 75, "c_obs": 150, "c_tot": 80,
            "sep":  10,
            "g_gr": 80, "g_fec": 80, "g_doc": 75, "g_obs": 150, "g_tot": 80,
        }
        tree_d = ttk.Treeview(det_tabla, columns=cols_d, show="headings",
                              selectmode="none", style=_STYLE)
        for c in cols_d:
            tree_d.heading(c, text=hdrs[c], anchor="center")
            anchor = "center" if c in ("c_tot", "g_tot", "sep", "c_fec", "g_fec") else "w"
            tree_d.column(c, width=widths[c], anchor=anchor,
                         stretch=(c != "sep"), minwidth=8 if c == "sep" else 40)

        vsb_d = ttk.Scrollbar(det_tabla, orient="vertical",   command=tree_d.yview)
        hsb_d = ttk.Scrollbar(det_tabla, orient="horizontal", command=tree_d.xview)
        tree_d.configure(yscrollcommand=vsb_d.set, xscrollcommand=hsb_d.set)
        vsb_d.pack(side="right",  fill="y")
        hsb_d.pack(side="bottom", fill="x")
        tree_d.pack(fill="both", expand=True)

        _tag_defaults(tree_d)

        for i, row in enumerate(rows):
            c_rec = row["compra"]
            g_rec = row["gasto"]
            tipo  = row["tipo"]
            vals = (
                _v(c_rec, "GRUPO"), _v(c_rec, "FECHA"), _v(c_rec, "NRO_DOC"),
                _v(c_rec, "ARTICULO"), _v(c_rec, "TOTAL"),
                "",
                _v(g_rec, "TIPO"), _v(g_rec, "FECHA"), _v(g_rec, "ORDEN"),
                _v(g_rec, "OBSERVACIONES"), _v(g_rec, "TOTAL"),
            )
            if tipo == "match":
                tag = "row_odd" if i % 2 == 0 else "row_even"
            else:
                tag = tipo
            tree_d.insert("", "end", values=vals, tags=(tag,))

        detail_frame.pack(fill="both", expand=True, pady=(8, 0))

    def _on_row_click(event):
        iid = tree.focus()
        if not iid or _df_c[0] is None:
            return
        tda = tree.item(iid, "values")[0]
        _mostrar_detalle(tda)

    tree.bind("<<TreeviewSelect>>", _on_row_click)


def _build_menaje(parent: tk.Widget) -> None:
    from modules import prm_menaje
    _build_resumen(parent, "🍽️  Diferencias Menaje",
                   prm_menaje.procesar_compras, prm_menaje.procesar_gastos,
                   bg_header="#2E7D32")


def _build_marketing(parent: tk.Widget) -> None:
    from modules import prm_marketing
    _build_resumen(parent, "📢  Diferencias Marketing",
                   prm_marketing.procesar_compras, prm_marketing.procesar_gastos,
                   bg_header="#E65100")


# ─────────────────────────────────────────────────────────────────────────────
# Movicaja / Compras — stubs (en desarrollo)
# ─────────────────────────────────────────────────────────────────────────────

def _build_stub(parent: tk.Widget, titulo: str, bg_header: str) -> None:
    hdr_top = tk.Frame(parent, bg=bg_header)
    hdr_top.pack(fill="x")
    tk.Label(hdr_top, text=f"  {titulo}",
             font=("Segoe UI", 12, "bold"),
             bg=bg_header, fg="white", pady=9).pack(side="left", padx=16)
    tk.Frame(parent, height=2, bg="#0D1B2A").pack(fill="x")

    body = tk.Frame(parent, bg="#0D1B2A")
    body.pack(fill="both", expand=True)
    tk.Label(body, text="🚧", font=("Segoe UI Emoji", 28),
             bg="#0D1B2A", fg="#546E7A").pack(pady=(80, 6))
    tk.Label(body, text="Módulo en desarrollo", font=("Segoe UI", 12, "bold"),
             bg="#0D1B2A", fg="#90A4AE").pack()
    tk.Label(body, text="Próximamente disponible dentro de este mismo panel.",
             font=("Segoe UI", 9), bg="#0D1B2A", fg="#607D8B").pack(pady=(4, 0))


def _build_movicaja(parent: tk.Widget) -> None:
    _build_stub(parent, "💰  Diferencias Movicaja", "#6A1B9A")


def _build_compras(parent: tk.Widget) -> None:
    _build_stub(parent, "🛒  Diferencias Compras", "#AD1457")
