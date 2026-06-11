import tkinter as tk
import ttkbootstrap as tb
from datetime import datetime, date as _date
import calendar as _cal


class CalendarioPopup(tk.Toplevel):
    _MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
              "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    _DIAS  = ["Do", "Lu", "Ma", "Mi", "Ju", "Vi", "Sá"]

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


class CampoFecha(tb.Frame):
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
        CalendarioPopup(self._ent, self.set_date, d)
