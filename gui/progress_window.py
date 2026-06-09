import tkinter as tk
from tkinter import ttk


class ProgressWindow:
    def __init__(self, parent, titulo="Procesando..."):
        self.top = tk.Toplevel(parent)
        self.top.title(titulo)
        self.top.geometry("400x120")
        self.top.resizable(False, False)

        self.top.transient(parent)
        self.top.grab_set()

        self.label = tk.Label(self.top, text="Iniciando...", anchor="w")
        self.label.pack(fill="x", padx=10, pady=(10, 5))

        self.progress = ttk.Progressbar(
            self.top,
            orient="horizontal",
            length=350,
            mode="determinate"
        )
        self.progress.pack(padx=10, pady=5)

        self.percent_label = tk.Label(self.top, text="0%")
        self.percent_label.pack(pady=(0, 10))

        self.top.update()

    def update(self, value, text=None):
        self.progress["value"] = value
        self.percent_label.config(text=f"{int(value)}%")

        if text:
            self.label.config(text=text)

        self.top.update_idletasks()

    def close(self):
        self.top.destroy()