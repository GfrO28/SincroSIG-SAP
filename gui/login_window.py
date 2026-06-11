# gui/login_window.py

import tkinter as tk
from tkinter import ttk
import ttkbootstrap as tb
from pathlib import Path


_APP_VERSION = "v1.0"


def mostrar_login(parent, on_success):
    """
    Muestra ventana de login como Toplevel modal del root.
    on_success(user_dict) se llama al autenticar correctamente.
    Bloquea hasta que el diálogo se cierre.
    """
    from config.auth import verificar_usuario_sig

    win = tb.Toplevel(parent)
    win.title("SincroSIG – Acceso")
    win.resizable(False, False)
    win.grab_set()   # modal

    # Centrar ventana con tamaño definitivo
    win.update_idletasks()
    w, h = 420, 540
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x  = (sw - w) // 2
    y  = (sh - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

    # ── Fondo / card ──────────────────────────────────────────────
    outer = tb.Frame(win, padding=0)
    outer.pack(fill="both", expand=True)

    card = tb.Frame(outer, padding=30)
    card.pack(fill="both", expand=True, padx=30, pady=30)

    # Logo / título
    tb.Label(card, text="⚙", font=("Segoe UI Emoji", 42),
             bootstyle="info").pack()
    tb.Label(card, text="SincroSIG",
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

    # Mostrar/ocultar contraseña
    var_ver = tk.BooleanVar(value=False)
    def _toggle_ver():
        ent_clave.config(show="" if var_ver.get() else "●")
    tb.Checkbutton(card, text="Mostrar contraseña", variable=var_ver,
                   bootstyle="secondary", command=_toggle_ver).pack(anchor="w", pady=(0, 16))

    # ── Mensaje de error ──────────────────────────────────────────
    lbl_error = tb.Label(card, text="", bootstyle="danger",
                         font=("Segoe UI", 9))
    lbl_error.pack(pady=(0, 8))

    # ── Botón ingresar ────────────────────────────────────────────
    btn_login = tb.Button(card, text="  Ingresar", bootstyle="info",
                          width=28, command=lambda: _do_login())
    btn_login.pack(fill="x")

    def _do_login(event=None):
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
            from tkinter import messagebox as _mb
            _mb.showerror("Error de configuración", str(e), parent=win)
            btn_login.config(state="normal", text="  Ingresar")
        except Exception:
            lbl_error.config(text="Error inesperado. Contacte al administrador.")
            btn_login.config(state="normal", text="  Ingresar")

    ent_clave.bind("<Return>", _do_login)
    ent_usuario.bind("<Return>", lambda e: ent_clave.focus_set())

    # ── Footer ────────────────────────────────────────────────────
    tb.Label(outer, text=f"SincroSIG {_APP_VERSION}  ·  © 2026",
             font=("Segoe UI", 8), bootstyle="secondary").pack(side="bottom", pady=6)

    ent_usuario.focus_set()
    parent.wait_window(win)   # bloquea hasta que el diálogo se destruya
