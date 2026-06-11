# gui / main_window.py

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import ttkbootstrap as tb

from config.db import get_connections
from config.utils import obtener_tiendas_sig
from controllers.formulaciones_controller import abrir_interfaz_formulaciones
from controllers.sync_controller import (
    sync_personal_controller,
    sync_estado_controller,
    sync_personaltienda_controller,
    sync_tiendas_controller,
    sync_detallecargo_controller,
    sync_cargos_controller
)
from controllers.validacion_controller import (
    validar_personaltienda_controller,
    abrir_validacion_formulaciones
)
from controllers.reconciliacion_controller import abrir_interfaz_reconciliacion

# ── Íconos (Twemoji 14 via jsDelivr CDN) ─────────────────────────────────────
_ICON_URLS = {
    "personal":      "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f465.png",
    "tiendas":       "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3ea.png",
    "cargos":        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4cb.png",
    "formulaciones": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9ea.png",
    "sap":           "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4ca.png",
}

_ICON_FALLBACK = {
    "personal":      "👥",
    "tiendas":       "🏪",
    "cargos":        "📋",
    "formulaciones": "🧪",
    "sap":           "📊",
}

_ICON_CACHE_DIR = Path(__file__).parent.parent / "assets" / "icons"
_loaded_photos  = {}   # evita GC de PhotoImage


def _cargar_icono(name: str, size: int = 72):
    """Descarga el ícono de internet (o usa caché local) y retorna PhotoImage."""
    try:
        from PIL import Image, ImageTk
        import requests

        _ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = _ICON_CACHE_DIR / f"{name}.png"

        if not cache_file.exists():
            url  = _ICON_URLS[name]
            resp = requests.get(url, timeout=6)
            resp.raise_for_status()
            cache_file.write_bytes(resp.content)

        img   = Image.open(str(cache_file)).convert("RGBA").resize((size, size), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        _loaded_photos[name] = photo   # anclar referencia
        return photo
    except Exception:
        return None


def _crear_modulo_card(parent, titulo, subtitulo, icono_name, comando, bg_accent):
    """Crea un card de módulo con ícono, título y botón."""
    frame = tb.Frame(parent, padding=6)
    frame.pack_propagate(False)
    frame.config(width=190, height=180)

    # Contenedor interno (botón completo)
    inner = tk.Frame(frame, cursor="hand2", relief="flat", bd=0,
                     bg=bg_accent, width=178, height=168)
    inner.pack(fill="both", expand=True)
    inner.pack_propagate(False)

    # ─ Ícono ─
    photo = _cargar_icono(icono_name, size=64)
    if photo:
        lbl_img = tk.Label(inner, image=photo, bg=bg_accent,
                           cursor="hand2")
        lbl_img.pack(pady=(14, 4))
    else:
        tk.Label(inner, text=_ICON_FALLBACK.get(icono_name, "?"),
                 font=("Segoe UI Emoji", 30), bg=bg_accent,
                 cursor="hand2").pack(pady=(14, 4))
        lbl_img = None

    # ─ Título ─
    tk.Label(inner, text=titulo, font=("Segoe UI", 10, "bold"),
             bg=bg_accent, fg="white", cursor="hand2").pack()
    if subtitulo:
        tk.Label(inner, text=subtitulo, font=("Segoe UI", 8),
                 bg=bg_accent, fg="#cccccc", cursor="hand2").pack()

    # Hacer todo el card clickeable
    def _click(_=None):
        comando()
    for w in [inner, lbl_img] + inner.winfo_children():
        if w:
            w.bind("<Button-1>", _click)
            w.bind("<Enter>", lambda _, f=inner: f.config(relief="ridge"))
            w.bind("<Leave>", lambda _, f=inner: f.config(relief="flat"))

    return frame


# ── Módulos ───────────────────────────────────────────────────────────────────
_PALETA = {
    "personal":      "#1565C0",   # azul profundo
    "tiendas":       "#2E7D32",   # verde
    "cargos":        "#6A1B9A",   # violeta
    "formulaciones": "#AD1457",   # rosa
    "sap":           "#E65100",   # naranja
}


def iniciar_en_root(root, user_info: dict | None = None):
    """
    Construye la interfaz principal dentro de un root existente.
    Llamar desde app.py después del login, antes de root.mainloop().
    """
    conn_sig, cur_sig, conn_web, cur_web = get_connections()

    root.title("SincroSIG")
    root.geometry("880x580")
    root.resizable(False, False)
    root.deiconify()    # mostrar ventana que estaba oculta

    # limpiar widgets del login si quedaron (por seguridad)
    for w in root.winfo_children():
        w.destroy()

    def _on_close():
        for obj in (cur_sig, cur_web, conn_sig, conn_web):
            try: obj.close()
            except Exception: pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    _construir_contenido(root, user_info, conn_sig, cur_sig, conn_web, cur_web)


def run_gui(user_info: dict | None = None):
    """Punto de entrada standalone (crea su propio root)."""
    conn_sig, cur_sig, conn_web, cur_web = get_connections()

    try:
        root = tb.Window(themename="superhero")
        root.title("SincroSIG")
        root.geometry("880x580")
        root.resizable(False, False)
        _construir_contenido(root, user_info, conn_sig, cur_sig, conn_web, cur_web)
        root.mainloop()
    finally:
        for obj in (cur_sig, cur_web, conn_sig, conn_web):
            try: obj.close()
            except Exception: pass


def _construir_contenido(root, user_info, conn_sig, cur_sig, conn_web, cur_web):
    """Puebla el root con el menú principal."""
    # ── Header ────────────────────────────────────────────────
    header = tb.Frame(root, padding=(16, 10, 16, 8))
    header.pack(fill="x")

    tb.Label(header, text="SincroSIG",
             font=("Segoe UI", 18, "bold"),
             bootstyle="info").pack(side="left")
    tb.Label(header, text="Sincronización SAP · SIG",
             font=("Segoe UI", 9),
             bootstyle="secondary").pack(side="left", padx=(8, 0), pady=(6, 0))

    if user_info:
        nombre   = user_info.get('nombre', '') or ''
        apellido = user_info.get('apellido', '') or ''
        cargo    = user_info.get('cargo', '') or user_info.get('desccargo', '')
        uid      = user_info.get('idusuario', '')
        etiqueta = f"  👤  {uid} – {apellido} {nombre}".strip()
        if cargo:
            etiqueta += f"  |  {cargo}"
        tb.Label(header, text=etiqueta,
                 font=("Segoe UI", 9),
                 bootstyle="secondary").pack(side="right", pady=(6, 0))

    ttk.Separator(root, orient="horizontal").pack(fill="x", padx=0)

    # ── Área de módulos ───────────────────────────────────────
    area = tb.Frame(root, padding=(20, 16))
    area.pack(fill="both", expand=True)

    tb.Label(area, text="Módulos del sistema",
             font=("Segoe UI", 11, "bold"),
             bootstyle="secondary").pack(anchor="w", pady=(0, 12))

    grid = tb.Frame(area)
    grid.pack(anchor="w")

    modulos = [
        ("PERSONAL",       "Empleados · Estado",
         "personal",       0, 0,
         lambda: _run_personal(root, cur_web, conn_web)),
        ("TIENDAS",        "Tiendas · Personal Tienda",
         "tiendas",        1, 0,
         lambda: _run_tiendas(root, cur_web, conn_web)),
        ("CARGOS",         "Cargo · Personal Cargo",
         "cargos",         2, 0,
         lambda: _run_cargos(root, cur_web, conn_web)),
        ("FORMULACIONES",  "TDA vs SIG · Reporte",
         "formulaciones",  3, 0,
         lambda: _run_formulaciones(root)),
        ("AJUSTES SAP",    "Reconciliación de Stock",
         "sap",            0, 1,
         lambda: abrir_interfaz_reconciliacion(root)),
    ]

    for titulo, sub, key, col, row, cmd in modulos:
        card = _crear_modulo_card(grid, titulo, sub, key, cmd, _PALETA[key])
        card.grid(row=row, column=col, padx=8, pady=8)

    # ── Footer ────────────────────────────────────────────────
    ttk.Separator(root, orient="horizontal").pack(fill="x", padx=0, side="bottom")
    footer = tb.Frame(root, padding=(16, 6))
    footer.pack(fill="x", side="bottom")

    tb.Button(footer, text="Salir", bootstyle="danger-outline",
              width=14, command=root.destroy).pack(side="right")

    tb.Label(footer, text="SincroSIG v1.0  ·  © 2026",
             font=("Segoe UI", 8),
             bootstyle="secondary").pack(side="left")


# ── Helpers para comandos agrupados ──────────────────────────────────────────

def _submenu(root, titulo, emoji, bg_header, items):
    """
    Crea un popup de submenú reutilizable.
    items: list of (emoji, label, bootstyle, comando)
    """
    sub = tb.Toplevel(root)
    sub.title(titulo)
    sub.geometry(f"340x{70 + len(items) * 54}")
    sub.resizable(False, False)
    sub.grab_set()

    # ── Header coloreado ──────────────────────────────────────
    hdr = tk.Frame(sub, bg=bg_header)
    hdr.pack(fill="x")
    tk.Label(hdr, text=f"{emoji}  {titulo}",
             font=("Segoe UI", 13, "bold"),
             bg=bg_header, fg="white", pady=12).pack()

    tk.Frame(sub, height=1, bg="#00000033").pack(fill="x")

    # ── Botones ───────────────────────────────────────────────
    body = tb.Frame(sub, padding=(14, 10, 14, 10))
    body.pack(fill="both", expand=True)

    for btn_emoji, texto, style, cmd in items:
        tb.Button(body,
                  text=f"  {btn_emoji}   {texto}",
                  bootstyle=style,
                  width=34,
                  command=lambda c=cmd: (sub.destroy(), c())
                  ).pack(fill="x", pady=4)

    return sub


def _run_personal(root, cur_web, conn_web):
    _submenu(root, "PERSONAL", "👥", "#1565C0", [
        ("👤", "Sincronizar Personal",        "info",
         lambda: sync_personal_controller(root, cur_web, conn_web)),
        ("🔄", "Sincronizar Estado Personal", "info",
         lambda: sync_estado_controller(root, cur_web, conn_web)),
    ])


def _run_tiendas(root, cur_web, conn_web):
    _submenu(root, "TIENDAS", "🏪", "#2E7D32", [
        ("🏬", "Sincronizar Tiendas",          "success",
         lambda: sync_tiendas_controller(root, cur_web, conn_web)),
        ("🔗", "Sincronizar Tienda Personal",  "success",
         lambda: sync_personaltienda_controller(root, cur_web, conn_web)),
        ("✅", "Verificar Personal Tienda",    "warning",
         lambda: validar_personaltienda_controller(root, cur_web, conn_web)),
    ])


def _run_cargos(root, cur_web, conn_web):
    _submenu(root, "CARGOS", "📋", "#6A1B9A", [
        ("🗂️",  "Sincronizar Cargo",           "secondary",
         lambda: sync_detallecargo_controller(root, cur_web, conn_web)),
        ("👥", "Sincronizar Personal Cargo",   "secondary",
         lambda: sync_cargos_controller(root, cur_web, conn_web)),
    ])


def _run_formulaciones(root):
    _submenu(root, "FORMULACIONES", "🧪", "#AD1457", [
        ("🔍", "Verificar Formulación TDA vs SIG", "danger",
         lambda: abrir_validacion_formulaciones(root, obtener_tiendas_sig)),
        ("📊", "Reporte Comparativo",              "primary",
         lambda: abrir_interfaz_formulaciones(root, obtener_tiendas_sig)),
    ])
