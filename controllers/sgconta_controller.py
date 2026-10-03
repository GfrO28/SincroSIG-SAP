# controllers/sgconta_controller.py
"""
Controlador del módulo SGCONTA (Personal · Tiendas · Cargos).
Ventana única maximizada: menú lateral + panel de contenido con las
acciones de sincronización de cada sección, agrupadas en cards.
"""

import tkinter as tk

from version import __version__
from controllers.sync_controller import (
    sync_personal_controller,
    sync_estado_controller,
    sync_personaltienda_controller,
    sync_tiendas_controller,
    sync_detallecargo_controller,
    sync_cargos_controller,
)
from controllers.validacion_controller import validar_personaltienda_controller


def abrir_sgconta(root: tk.Misc, cur_web, conn_web) -> None:
    """
    Ventana única del módulo SGCONTA: menú lateral fijo (Personal, Tiendas,
    Cargos) y panel de contenido con las acciones de cada sección. Cada
    acción conserva su flujo actual (ventana de progreso, confirmación y
    ejecución del SQL generado).
    """
    win = tk.Toplevel(root)
    win.title("SGCONTA – Personal · Tiendas · Cargos")
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
    tk.Label(brand, text="SGCONTA", font=("Segoe UI", 18, "bold"),
             bg=_SIDEBAR_BG, fg="#42A5F5").pack(anchor="w")
    tk.Label(brand, text="Personal · Tiendas · Cargos", font=("Segoe UI", 8),
             bg=_SIDEBAR_BG, fg="#78909C").pack(anchor="w", pady=(2, 0))
    tk.Frame(sidebar, height=1, bg="#16304A").pack(fill="x", padx=18, pady=(0, 8))

    nav_frame = tk.Frame(sidebar, bg=_SIDEBAR_BG)
    nav_frame.pack(fill="both", expand=True, padx=10)

    tk.Frame(sidebar, height=1, bg="#16304A").pack(fill="x", padx=18, pady=(8, 0))
    tk.Label(sidebar, text=f"SincroSIG · v{__version__}", bg=_SIDEBAR_BG, fg="#546E7A",
             font=("Segoe UI", 7)).pack(pady=(8, 14))

    # ── Acciones por sección (icono, título, descripción, color, comando) ─
    def _acciones_personal():
        return [
            ("👤", "Sincronizar Personal",
             "Inserta y actualiza personal desde SAP hacia SIG.", "#3498DB",
             lambda: sync_personal_controller(win, cur_web, conn_web)),
            ("🔄", "Sincronizar Estado Personal",
             "Actualiza el estado (activo/inactivo) del personal.", "#3498DB",
             lambda: sync_estado_controller(win, cur_web, conn_web)),
        ]

    def _acciones_tiendas():
        return [
            ("🏬", "Sincronizar Tiendas",
             "Inserta tiendas faltantes en SIG.", "#2ECC71",
             lambda: sync_tiendas_controller(win, cur_web, conn_web)),
            ("🔗", "Sincronizar Tienda Personal",
             "Sincroniza la relación tienda-personal.", "#2ECC71",
             lambda: sync_personaltienda_controller(win, cur_web, conn_web)),
            ("✅", "Verificar Personal Tienda",
             "Valida consistencia de personal por tienda.", "#F39C12",
             lambda: validar_personaltienda_controller(win, cur_web, conn_web)),
        ]

    def _acciones_cargos():
        return [
            ("🗂️", "Sincronizar Cargo",
             "Inserta detalle de cargo faltante.", "#7F8C8D",
             lambda: sync_detallecargo_controller(win, cur_web, conn_web)),
            ("👥", "Sincronizar Personal Cargo",
             "Sincroniza el cargo asignado por personal.", "#7F8C8D",
             lambda: sync_cargos_controller(win, cur_web, conn_web)),
        ]

    modulos = [
        ("personal", "👤", "Personal", "#1565C0", _acciones_personal),
        ("tiendas",  "🏪", "Tiendas",  "#2E7D32", _acciones_tiendas),
        ("cargos",   "📋", "Cargos",   "#6A1B9A", _acciones_cargos),
    ]

    nav_widgets = {}
    builders = {}
    for mod_id, icon, label, color, acciones_fn in modulos:
        builders[mod_id] = (icon, label, color, acciones_fn)
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
            icon, label, color, acciones_fn = builders[mod_id]
            frame = tk.Frame(content, bg="#0D1B2A")
            frame.grid(row=0, column=0, sticky="nsew")
            _build_acciones(frame, f"{icon}  {label}", color, acciones_fn())
            _tab_frames[mod_id] = frame
        return _tab_frames[mod_id]

    def _switch_tab(mod_id):
        _get_or_build(mod_id).tkraise()
        _set_active(mod_id)

    _switch_tab("personal")


def _build_acciones(parent: tk.Widget, titulo: str, bg_header: str,
                     acciones: list) -> None:
    """
    Pinta el header coloreado y la lista de cards de acción dentro de `parent`.
    acciones: lista de tuplas (icono, titulo, descripcion, color_accent, comando).
    """
    hdr_top = tk.Frame(parent, bg=bg_header)
    hdr_top.pack(fill="x")
    tk.Label(hdr_top, text=f"  {titulo}", font=("Segoe UI", 12, "bold"),
             bg=bg_header, fg="white", pady=9).pack(side="left", padx=16)
    tk.Frame(parent, height=2, bg="#0D1B2A").pack(fill="x")

    body = tk.Frame(parent, bg="#0D1B2A")
    body.pack(fill="both", expand=True, padx=20, pady=16)

    tk.Label(body,
             text=("Selecciona una acción para ejecutar la sincronización. "
                   "Cada una muestra su propia ventana de progreso y pide "
                   "confirmación antes de aplicar los cambios."),
             bg="#0D1B2A", fg="#78909C", font=("Segoe UI", 9),
             wraplength=640, justify="left").pack(anchor="w", pady=(0, 10))

    for icon, title, desc, accent, cmd in acciones:
        card = tk.Frame(body, bg="#122036")
        card.pack(fill="x", pady=5)

        tk.Frame(card, width=4, bg=accent).pack(side="left", fill="y")

        inner = tk.Frame(card, bg="#122036")
        inner.pack(side="left", fill="both", expand=True, padx=(12, 8), pady=10)

        tk.Label(inner, text=icon, font=("Segoe UI Emoji", 16),
                 bg="#122036", fg="#ECEFF1").pack(side="left", padx=(0, 10))

        txt = tk.Frame(inner, bg="#122036")
        txt.pack(side="left", fill="both", expand=True)
        tk.Label(txt, text=title, font=("Segoe UI", 10, "bold"),
                 bg="#122036", fg="#ECEFF1", anchor="w").pack(anchor="w")
        tk.Label(txt, text=desc, font=("Segoe UI", 8),
                 bg="#122036", fg="#90A4AE", anchor="w",
                 wraplength=560, justify="left").pack(anchor="w")

        tk.Button(card, text="Ejecutar", command=cmd, bg=accent, fg="white",
                  activebackground=accent, activeforeground="white",
                  relief="flat", bd=0, font=("Segoe UI", 9, "bold"),
                  padx=14, pady=6, cursor="hand2").pack(side="right", padx=14)
