# gui/login_window.py

import queue
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import ttkbootstrap as tb
from PIL import Image, ImageTk

from version import __version__, APP_NAME


def _load_logo(size: int = 64) -> ImageTk.PhotoImage | None:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
    ico  = base / "assets" / "icon.ico"
    try:
        img = Image.open(ico).convert("RGBA").resize((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def mostrar_login(parent, on_success):
    """
    Muestra ventana de login como Toplevel modal del root.
    on_success(user_dict) se llama al autenticar correctamente.
    Bloquea hasta que el diálogo se cierre.
    """
    from config.auth import verificar_usuario_sig

    win = tb.Toplevel(parent)
    win.title(f"{APP_NAME} – Acceso")
    win.resizable(False, False)
    win.grab_set()

    # Icono de ventana y taskbar
    try:
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
        win.iconbitmap(str(base / "assets" / "icon.ico"))
    except Exception:
        pass

    win.update_idletasks()
    w, h = 420, 640
    sw   = win.winfo_screenwidth()
    sh   = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── Fondo / card ──────────────────────────────────────────────
    outer = tb.Frame(win, padding=0)
    outer.pack(fill="both", expand=True)

    card = tb.Frame(outer, padding=30)
    card.pack(fill="both", expand=True, padx=30, pady=(30, 8))

    # Logo / título
    _logo_img = _load_logo(64)
    if _logo_img:
        lbl_logo = tb.Label(card, image=_logo_img)
        lbl_logo.image = _logo_img  # evitar GC
        lbl_logo.pack()
    else:
        tb.Label(card, text="🔄", font=("Segoe UI Emoji", 42), bootstyle="info").pack()
    tb.Label(card, text=APP_NAME,
             font=("Segoe UI", 22, "bold")).pack(pady=(4, 0))
    tb.Label(card, text="Sistema de Sincronización SAP · SIG",
             font=("Segoe UI", 9), bootstyle="secondary").pack(pady=(2, 20))

    # ── Campos ────────────────────────────────────────────────────
    tb.Label(card, text="ID Usuario", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    var_usuario = tk.StringVar()
    ent_usuario = tb.Entry(card, textvariable=var_usuario, font=("Segoe UI", 11), width=32)
    ent_usuario.pack(fill="x", pady=(2, 12))

    tb.Label(card, text="Contraseña", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    var_clave = tk.StringVar()
    ent_clave = tb.Entry(card, textvariable=var_clave, show="●",
                         font=("Segoe UI", 11), width=32)
    ent_clave.pack(fill="x", pady=(2, 6))

    var_ver = tk.BooleanVar(value=False)
    def _toggle_ver():
        ent_clave.config(show="" if var_ver.get() else "●")
    tb.Checkbutton(card, text="Mostrar contraseña", variable=var_ver,
                   bootstyle="secondary", command=_toggle_ver).pack(anchor="w", pady=(0, 16))

    # ── Mensaje de error ──────────────────────────────────────────
    lbl_error = tb.Label(card, text="", bootstyle="danger", font=("Segoe UI", 9))
    lbl_error.pack(pady=(0, 8))

    # ── Botón ingresar ────────────────────────────────────────────
    btn_login = tb.Button(card, text="  Ingresar", bootstyle="info",
                          width=28, command=lambda: _do_login())
    btn_login.pack(fill="x")

    def _do_login(_event=None):
        uid   = var_usuario.get().strip()
        clave = var_clave.get()
        if not uid or not clave:
            lbl_error.config(text="Complete todos los campos.")
            return
        btn_login.config(state="disabled", text="Verificando…")
        win.update()
        try:
            row = verificar_usuario_sig(uid, clave)
            if row:
                lbl_error.config(text="")
                win.destroy()
                on_success(row)
            else:
                lbl_error.config(text="Usuario o contraseña incorrectos.")
                btn_login.config(state="normal", text="  Ingresar")
        except (ConnectionError, EnvironmentError) as e:
            messagebox.showerror("Error de configuración", str(e), parent=win)
            btn_login.config(state="normal", text="  Ingresar")
        except Exception:
            lbl_error.config(text="Error inesperado. Contacte al administrador.")
            btn_login.config(state="normal", text="  Ingresar")

    ent_clave.bind("<Return>", lambda _e: _do_login())
    ent_usuario.bind("<Return>", lambda _e: ent_clave.focus_set())

    # ── Footer: versión + botón de actualización ──────────────────
    ttk.Separator(outer, orient="horizontal").pack(fill="x", padx=30)
    footer = tb.Frame(outer, padding=(30, 8, 30, 12))
    footer.pack(fill="x")

    tb.Label(footer, text=f"{APP_NAME} v{__version__}  ·  © 2026",
             font=("Segoe UI", 8), bootstyle="secondary").pack(side="left")

    btn_update = tb.Button(
        footer, text="🔄 Buscar actualizaciones",
        bootstyle="secondary-outline",
        command=lambda: _verificar_update(),
    )
    btn_update.pack(side="right")

    # ── Lógica de actualización ───────────────────────────────────
    def _verificar_update():
        btn_update.config(state="disabled", text="Verificando…")
        win.update()

        _q = queue.Queue()

        def _tarea():
            try:
                from modules.updater import verificar_actualizacion
                info = verificar_actualizacion()
                _q.put(("ok", info))
            except Exception as e:
                _q.put(("error", str(e)))

        def _poll():
            try:
                tipo, payload = _q.get_nowait()
                if tipo == "ok":
                    _mostrar_resultado(payload)
                else:
                    _error_update(payload)
            except queue.Empty:
                win.after(100, _poll)

        threading.Thread(target=_tarea, daemon=True).start()
        win.after(100, _poll)

    def _mostrar_resultado(info):
        if info is None:
            btn_update.config(
                state="normal",
                text=f"✓  v{__version__} — actualizado",
                bootstyle="success-outline",
            )
            messagebox.showinfo(
                "Sin actualizaciones",
                f"Ya tienes la versión más reciente.\n\nVersión actual: v{__version__}",
                parent=win,
            )
            return

        # Hay nueva versión disponible
        btn_update.config(state="normal", text="🔄 Buscar actualizaciones",
                          bootstyle="secondary-outline")
        notas = info['notas'][:400] + ("…" if len(info['notas']) > 400 else "")
        respuesta = messagebox.askyesno(
            "Nueva versión disponible",
            f"Versión disponible:  {info['version']}\n"
            f"Versión actual:       v{__version__}\n\n"
            f"{notas}\n\n"
            f"¿Instalar ahora?",
            parent=win,
        )
        if respuesta:
            if not info.get("url_descarga"):
                messagebox.showwarning(
                    "Sin instalador",
                    "El release no tiene un instalador adjunto.\n"
                    "Descargalo manualmente desde GitHub.",
                    parent=win,
                )
                return
            _iniciar_descarga(info)

    def _iniciar_descarga(info):
        from gui.progress_window import ProgressWindow
        from modules.updater import descargar_e_instalar

        prog = ProgressWindow(win, f"Descargando {info['version']}…")
        prog.update(0, "Conectando con GitHub…")
        btn_update.config(state="disabled")

        _dl_q = queue.Queue()

        def _progreso(pct):
            _dl_q.put(("pct", pct))

        def _on_error(msg):
            _dl_q.put(("error", msg))

        def _poll_dl():
            try:
                while True:
                    kind, val = _dl_q.get_nowait()
                    if kind == "error":
                        _fallo_descarga(val, prog)
                        return
                    prog.update(val, f"Descargando… {val:.0f}%")
            except queue.Empty:
                pass
            try:
                if prog.winfo_exists():
                    win.after(150, _poll_dl)
            except Exception:
                pass

        win.after(150, _poll_dl)
        descargar_e_instalar(info, progreso_fn=_progreso, on_error=_on_error)

    def _fallo_descarga(msg, prog):
        prog.close()
        btn_update.config(state="normal")
        messagebox.showerror("Error al descargar", msg, parent=win)

    def _error_update(msg):
        btn_update.config(state="normal", text="🔄 Buscar actualizaciones",
                          bootstyle="secondary-outline")
        messagebox.showerror("Error", f"No se pudo verificar actualizaciones:\n{msg}", parent=win)

    ent_usuario.focus_set()
    parent.wait_window(win)
