# gui/progress_window.py

import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import DETERMINATE


class ProgressWindow:
    """Ventana modal de progreso para operaciones largas (ej: descarga del instalador)."""

    def __init__(self, parent, titulo: str = "Procesando…"):
        self._win = tb.Toplevel(parent)
        self._win.title(titulo)
        self._win.resizable(False, False)
        self._win.transient(parent)
        self._win.grab_set()
        self._win.protocol("WM_DELETE_WINDOW", lambda: None)  # no cerrable manualmente

        w, h = 400, 130
        self._win.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self._win.geometry(f"{w}x{h}+{max(0, px)}+{max(0, py)}")

        frame = tb.Frame(self._win, padding=20)
        frame.pack(fill="both", expand=True)

        self._lbl = tb.Label(frame, text="Iniciando…", font=("Segoe UI", 9), anchor="w")
        self._lbl.pack(fill="x", pady=(0, 8))

        self._var = tk.DoubleVar(value=0)
        self._bar = tb.Progressbar(
            frame, variable=self._var,
            mode=DETERMINATE, bootstyle="info-striped",
            length=360,
        )
        self._bar.pack(fill="x")

        self._pct_lbl = tb.Label(frame, text="0%", font=("Segoe UI", 8),
                                 bootstyle="secondary")
        self._pct_lbl.pack(anchor="e", pady=(4, 0))

        self._win.update()

    def update(self, value: float, text: str = ""):
        self._var.set(value)
        self._pct_lbl.config(text=f"{int(value)}%")
        if text:
            self._lbl.config(text=text)
        self._win.update_idletasks()

    def close(self):
        try:
            self._win.destroy()
        except tk.TclError:
            pass
