import tkinter as tk
from tkinter import ttk


class SearchableCheckList:
    def __init__(self, parent, items, height=400):
        """
        items: lista de tuplas (id, texto_mostrar)
        """
        self.parent = parent
        self.original_items = items  # datos originales
        self.filtered_items = items

        self.vars = {}  # id -> BooleanVar

        # -------------------------
        # FRAME PRINCIPAL
        # -------------------------
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="both", expand=True)

        # -------------------------
        # BUSCADOR
        # -------------------------
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._filtrar)

        entry = ttk.Entry(self.frame, textvariable=self.search_var)
        entry.pack(fill="x", padx=5, pady=5)

        # -------------------------
        # SELECT ALL
        # -------------------------
        self.select_all_var = tk.BooleanVar()

        chk_all = ttk.Checkbutton(
            self.frame,
            text="Seleccionar todas",
            variable=self.select_all_var,
            command=self._toggle_all
        )
        chk_all.pack(anchor="w", padx=5)

        # -------------------------
        # SCROLL AREA
        # -------------------------
        contenedor = ttk.Frame(self.frame)
        contenedor.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(contenedor, height=height)
        scrollbar = ttk.Scrollbar(contenedor, orient="vertical", command=self.canvas.yview)

        self.inner_frame = ttk.Frame(self.canvas)

        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._configurar_mousewheel()

        # Inicializar lista
        self._render_items()

    # ==========================================
    # RENDERIZADO
    # ==========================================
    def _render_items(self):
        # Limpiar
        for widget in self.inner_frame.winfo_children():
            widget.destroy()

        for item_id, text in self.filtered_items:
            if item_id not in self.vars:
                self.vars[item_id] = tk.BooleanVar()

            chk = ttk.Checkbutton(
                self.inner_frame,
                text=text,
                variable=self.vars[item_id]
            )
            chk.pack(anchor="w", fill="x", padx=5, pady=2)

    # ==========================================
    # FILTRO
    # ==========================================
    def _filtrar(self, *args):
        texto = self.search_var.get().lower()

        if not texto:
            self.filtered_items = self.original_items
        else:
            self.filtered_items = [
                (i, t) for i, t in self.original_items
                if texto in t.lower()
            ]

        self._render_items()

    # ==========================================
    # SELECT ALL
    # ==========================================
    def _toggle_all(self):
        estado = self.select_all_var.get()

        for item_id, _ in self.filtered_items:
            self.vars[item_id].set(estado)

    # ==========================================
    # OBTENER SELECCIONADOS
    # ==========================================
    def get_selected(self):
        return [item_id for item_id, var in self.vars.items() if var.get()]

    # ==========================================
    # LIMPIAR SELECCION
    # ==========================================
    def clear_selection(self):
        for var in self.vars.values():
            var.set(False)

    # ==========================================
    # SET ITEMS (REUTILIZAR COMPONENTE)
    # ==========================================
    def set_items(self, items):
        """
        Permite reutilizar el componente con nuevos datos
        """
        self.original_items = items
        self.filtered_items = items
        self.vars.clear()
        self.select_all_var.set(False)
        self._render_items()

    def set_checked(self, ids):
        for k, v in self.vars.items():
            v.set(k in ids)

    def _configurar_mousewheel(self):

        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")

        self.frame.bind("<Enter>", _bind_mousewheel)
        self.frame.bind("<Leave>", _unbind_mousewheel)