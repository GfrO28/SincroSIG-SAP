# controllers/formulaciones_controller.py

import tkinter as tk
from tkinter import ttk
import threading
import os
from tkinter import messagebox
import ttkbootstrap as tb
from version import __version__
from gui.searchable_checklist import SearchableCheckList
from config.db import get_store_connection, get_sig_connection
from modules import filtro_insumos, validar_faltantes_formulacion, validar_formulacion_detalle
from modules.formulaciones_engine import construir_dataset_formulaciones
from modules.formulaciones_export import exportar_excel_dataset
from gui.progress_window import ProgressWindow
from modules.preciart_service import articulo_valido_para_formulacion
from modules.formulaciones_service import (
    obtener_formulas_por_insumos,
    obtener_formulaciones_por_texto,
    obtener_idformulacion_batch_multi,
    obtener_detalles_formulaciones_batch,
    obtener_detalle_formulacion,
)

_SIDEBAR_BG = "#0A1420"


# ==========================================
# VENTANA ÚNICA — menú lateral + panel de contenido
# ==========================================
def abrir_formulaciones(root: tk.Misc, obtener_tiendas_sig) -> None:
    """
    Ventana única del módulo Formulaciones: menú lateral fijo (Verificación,
    Reporte Comparativo) y panel de contenido que cambia según la sección
    seleccionada, maximizada y ajustada al redimensionar.
    """
    win = tk.Toplevel(root)
    win.title("Formulaciones – Verificación y Reporte")
    try:
        win.state("zoomed")
    except tk.TclError:
        win.attributes("-zoomed", True)
    win.minsize(1024, 650)

    win.columnconfigure(0, weight=0)
    win.columnconfigure(1, weight=1)
    win.rowconfigure(0, weight=1)

    # Tiendas: se obtienen una sola vez por apertura y se comparten entre
    # ambas pestañas (antes cada una pedía su propia copia por separado).
    try:
        tiendas = obtener_tiendas_sig()
    except Exception as e:
        tiendas = []
        messagebox.showerror("Error", f"No se pudieron obtener las tiendas:\n{e}", parent=win)

    sidebar = tk.Frame(win, bg=_SIDEBAR_BG, width=216)
    sidebar.grid(row=0, column=0, sticky="ns")
    sidebar.grid_propagate(False)

    content = tk.Frame(win, bg="#0D1B2A")
    content.grid(row=0, column=1, sticky="nsew")
    content.rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)

    # ── Marca ────────────────────────────────────────────────────────────
    brand = tk.Frame(sidebar, bg=_SIDEBAR_BG)
    brand.pack(fill="x", padx=18, pady=(18, 14))
    tk.Label(brand, text="FORMULACIONES", font=("Segoe UI", 14, "bold"),
             bg=_SIDEBAR_BG, fg="#42A5F5").pack(anchor="w")
    tk.Label(brand, text="Verificación · Reporte", font=("Segoe UI", 8),
             bg=_SIDEBAR_BG, fg="#78909C").pack(anchor="w", pady=(2, 0))
    tk.Frame(sidebar, height=1, bg="#16304A").pack(fill="x", padx=18, pady=(0, 8))

    nav_frame = tk.Frame(sidebar, bg=_SIDEBAR_BG)
    nav_frame.pack(fill="both", expand=True, padx=10)

    tk.Frame(sidebar, height=1, bg="#16304A").pack(fill="x", padx=18, pady=(8, 0))
    tk.Label(sidebar, text=f"SincroSIG · v{__version__}", bg=_SIDEBAR_BG, fg="#546E7A",
             font=("Segoe UI", 7)).pack(pady=(8, 14))

    modulos = [
        ("verificacion", "🔍", "Verificación TDA vs SIG", "#C62828",
         lambda p: _build_verificacion(p, win, tiendas)),
        ("reporte",      "📊", "Reporte Comparativo",      "#1565C0",
         lambda p: _build_reporte(p, win, tiendas)),
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

    _switch_tab("verificacion")


# ==========================================
# VERIFICACIÓN TDA vs SIG
# ==========================================
def _build_verificacion(parent: tk.Widget, win: tk.Misc, tiendas: list) -> None:
    _BG_HDR = "#C62828"
    hdr_top = tk.Frame(parent, bg=_BG_HDR)
    hdr_top.pack(fill="x")
    tk.Label(hdr_top, text="🔍  Verificación TDA vs SIG", font=("Segoe UI", 12, "bold"),
             bg=_BG_HDR, fg="white", pady=9).pack(side="left", padx=16)
    tk.Frame(parent, height=2, bg="#0D1B2A").pack(fill="x")

    body = tk.Frame(parent, bg="#0D1B2A")
    body.pack(fill="both", expand=True, padx=20, pady=16)

    tk.Label(body, text="Selecciona las tiendas para validar la formulación TDA vs SIG.",
             bg="#0D1B2A", fg="#78909C", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

    card = tk.Frame(body, bg="#122036")
    card.pack(fill="both", expand=True, pady=(0, 12))
    tk.Label(card, text="TIENDAS", bg="#122036", fg="#90A4AE",
             font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

    frame_content = tk.Frame(card, bg="#122036")
    frame_content.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    lista_tiendas = SearchableCheckList(
        frame_content,
        [(t_id, nombre) for t_id, nombre, *_ in tiendas]
    )

    def ejecutar_validacion_faltantes():
        seleccionadas = lista_tiendas.get_selected()
        if not seleccionadas:
            messagebox.showwarning("Atención", "Debes seleccionar al menos una tienda.", parent=win)
            return

        progress = ProgressWindow(win, "Verificando formulaciones…")

        def _tarea():
            try:
                n = len(seleccionadas)
                progress.update(10, f"Procesando {n} tienda(s)…")
                ruta = validar_faltantes_formulacion.validar_faltantes_formulacion_varias(
                    seleccionadas, nombre_archivo=None
                )
                progress.update(100, "Completado")
                win.after(0, lambda: (
                    progress.close(),
                    messagebox.showinfo("Validación completada", f"Archivo generado:\n{ruta}", parent=win)
                ))
            except ConnectionError as e:
                win.after(0, lambda m=str(e): (
                    progress.close(),
                    messagebox.showwarning("Completado con advertencias", m, parent=win)
                ))
            except Exception as e:
                win.after(0, lambda m=str(e): (
                    progress.close(),
                    messagebox.showerror("Error", f"Ocurrió un error:\n{m}", parent=win)
                ))

        threading.Thread(target=_tarea, daemon=True).start()

    def ejecutar_validacion_detalle():
        seleccionadas = lista_tiendas.get_selected()
        if not seleccionadas:
            messagebox.showwarning("Atención", "Debes seleccionar al menos una tienda.", parent=win)
            return

        progress = ProgressWindow(win, "Verificando detalle de formulaciones…")

        def _tarea():
            try:
                n = len(seleccionadas)
                progress.update(10, f"Procesando {n} tienda(s)…")
                ruta = validar_formulacion_detalle.validar_formulacion_detalle_varias(seleccionadas)
                progress.update(100, "Completado")
                win.after(0, lambda: (
                    progress.close(),
                    messagebox.showinfo("Validación completada", f"Archivo generado:\n{ruta}", parent=win)
                ))
            except ConnectionError as e:
                win.after(0, lambda m=str(e): (
                    progress.close(),
                    messagebox.showwarning("Completado con advertencias", m, parent=win)
                ))
            except Exception as e:
                win.after(0, lambda m=str(e): (
                    progress.close(),
                    messagebox.showerror("Error", f"Ocurrió un error:\n{m}", parent=win)
                ))

        threading.Thread(target=_tarea, daemon=True).start()

    botones = tk.Frame(body, bg="#0D1B2A")
    botones.pack(fill="x")

    tk.Button(botones, text="Validar Faltantes", command=ejecutar_validacion_faltantes,
              bg="#C62828", fg="white", activebackground="#C62828", activeforeground="white",
              relief="flat", bd=0, font=("Segoe UI", 9, "bold"), padx=18, pady=8,
              cursor="hand2").pack(side="left", padx=(0, 10))

    tk.Button(botones, text="Validar Detalle", command=ejecutar_validacion_detalle,
              bg="#0D1B2A", fg="#64B5F6", activebackground="#0D1B2A", activeforeground="#90CAF9",
              relief="flat", bd=1, highlightbackground="#1565C0", highlightthickness=1,
              font=("Segoe UI", 9, "bold"), padx=18, pady=8, cursor="hand2").pack(side="left")


# ==========================================
# REPORTE COMPARATIVO
# ==========================================
def _build_reporte(parent: tk.Widget, win: tk.Misc, tiendas: list) -> None:
    _BG_HDR = "#1565C0"
    hdr_top = tk.Frame(parent, bg=_BG_HDR)
    hdr_top.pack(fill="x")
    tk.Label(hdr_top, text="📊  Reporte Comparativo", font=("Segoe UI", 12, "bold"),
             bg=_BG_HDR, fg="white", pady=9).pack(side="left", padx=16)
    tk.Frame(parent, height=2, bg="#0D1B2A").pack(fill="x")

    body = tk.Frame(parent, bg="#0D1B2A")
    body.pack(fill="both", expand=True, padx=20, pady=16)

    def crear_panel(parent_p, titulo):
        card = tk.Frame(parent_p, bg="#122036")
        card.pack(side="left", fill="both", expand=True, padx=(0, 7))
        tk.Label(card, text=titulo, bg="#122036", fg="#90A4AE",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        frame_top = tk.Frame(card, bg="#122036")
        frame_top.pack(fill="x", padx=10)
        frame_content = tk.Frame(card, bg="#122036")
        frame_content.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        return frame_top, frame_content

    paneles = tk.Frame(body, bg="#0D1B2A")
    paneles.pack(fill="both", expand=True, pady=(0, 12))

    frame_t_top, frame_t_content = crear_panel(paneles, "TIENDAS")
    frame_f_top, frame_f_content = crear_panel(paneles, "FORMULACIONES")

    # ── Tiendas (ya cargadas al abrir la ventana) ──────────────────────────
    lista_tiendas = SearchableCheckList(
        frame_t_content,
        [(idtienda, nombre) for idtienda, nombre, _tipo in tiendas]
    )
    tipos_tienda = {idtienda: tipo for idtienda, _nombre, tipo in tiendas}

    def filtrar_tipo(tipo):
        ids = [tid for tid, t in tipos_tienda.items() if t == tipo]
        lista_tiendas.set_checked(ids)

    tb.Button(frame_t_top, text="Hoteles", bootstyle="secondary-outline",
              command=lambda: filtrar_tipo(3)).pack(side="left", padx=(0, 4), pady=(0, 6))
    tb.Button(frame_t_top, text="Lima", bootstyle="secondary-outline",
              command=lambda: filtrar_tipo(1)).pack(side="left", padx=(0, 4), pady=(0, 6))
    tb.Button(frame_t_top, text="Provincia", bootstyle="secondary-outline",
              command=lambda: filtrar_tipo(2)).pack(side="left", pady=(0, 6))

    # ── Formulaciones: sin precarga, se buscan a demanda ───────────────────
    def buscar_formulas_remoto(texto):
        try:
            resultados = obtener_formulaciones_por_texto(texto, limite=50)
        except Exception:
            return []
        return [(idart, f"{idart} - {desc}") for idart, desc in resultados]

    lista_formulas = SearchableCheckList(
        frame_f_content, [], on_search=buscar_formulas_remoto, min_chars=2
    )

    btn_reset = tb.Button(frame_f_top, text="Quitar filtro",
                           bootstyle="secondary-outline", state="disabled")
    btn_reset.pack(side="left", padx=(4, 0), pady=(0, 6))

    def filtrar_por_insumo():
        seleccion = filtro_insumos.seleccionar_insumo(win)
        if not seleccion:
            return

        id_insumo, _ = seleccion
        conn_sig, cur_sig = get_sig_connection()
        try:
            validas = obtener_formulas_por_insumos(cur_sig, [id_insumo])
        finally:
            cur_sig.close()
            conn_sig.close()

        nuevas = [(idart, f"{idart} - {desc}") for idart, desc in validas]
        lista_formulas.set_items(nuevas, reset_selection=False)
        btn_reset.config(state="normal")

    def reset_filtro():
        lista_formulas.set_items([], reset_selection=False)
        btn_reset.config(state="disabled")

    tb.Button(frame_f_top, text="Filtrar por insumo", bootstyle="secondary-outline",
              command=filtrar_por_insumo).pack(side="left", pady=(0, 6))
    btn_reset.config(command=reset_filtro)

    # ── Generar reporte ──────────────────────────────────────────────────
    def generar(solo_diferencias=False):
        tdas = lista_tiendas.get_selected()
        forms = list(map(int, lista_formulas.get_selected()))

        if not tdas:
            messagebox.showwarning("Aviso", "Seleccione al menos una tienda", parent=win)
            return
        if not forms:
            messagebox.showwarning("Aviso", "Seleccione al menos una formulación", parent=win)
            return

        progress = ProgressWindow(win, "Generando reporte...")

        def tarea():
            conn_sig = None
            cur_val = None
            try:
                conn_sig, cur_val = get_sig_connection()

                tipo_por_tienda = {int(t[0]): int(t[2]) for t in tiendas}

                base_por_tipo = {1: 3, 2: 34, 3: 41}

                cache_idforms = {}
                try:
                    cache_idforms = obtener_idformulacion_batch_multi(cur_val, tdas, forms)
                except Exception as e:
                    print("ERROR CACHE IDFORMS:", e)
                    cache_idforms = {}

                cache_detalles = {}
                if cache_idforms:
                    try:
                        cache_detalles = obtener_detalles_formulaciones_batch(
                            cur_val, list(cache_idforms.values())
                        )
                    except Exception:
                        cache_detalles = {}

                dataset = construir_dataset_formulaciones(
                    articulos=forms,
                    tiendas=tdas,
                    tipo_por_tienda=tipo_por_tienda,
                    base_por_tipo=base_por_tipo,
                    cache_idforms=cache_idforms,
                    cache_detalles=cache_detalles,
                    cur_val=cur_val,
                    get_store_connection=get_store_connection,
                    obtener_detalle_formulacion=obtener_detalle_formulacion,
                    articulo_valido_para_formulacion=articulo_valido_para_formulacion,
                    progress_callback=lambda p, m: progress.update(p, m)
                )

                if not dataset or not dataset.get("articulos"):
                    raise Exception("Dataset vacío: no se generó ninguna formulación")

                ruta = exportar_excel_dataset(
                    dataset=dataset,
                    tiendas=tdas,
                    solo_diferencias=solo_diferencias,
                    base_por_tipo=base_por_tipo,
                )

                if not ruta or not os.path.exists(ruta):
                    raise Exception("El Excel no se generó correctamente")

                def finalizar():
                    progress.close()
                    messagebox.showinfo("Éxito", f"Reporte generado:\n{ruta}", parent=win)

                progress.top.after(0, finalizar)

            except Exception as e:
                import traceback
                err = traceback.format_exc()
                print(err)

                def error_ui():
                    progress.close()
                    messagebox.showerror("Error", err, parent=win)

                progress.top.after(0, error_ui)

            finally:
                try:
                    if cur_val:
                        cur_val.close()
                    if conn_sig:
                        conn_sig.close()
                except Exception:
                    pass

        threading.Thread(target=tarea, daemon=True).start()

    botones = tk.Frame(body, bg="#0D1B2A")
    botones.pack(fill="x")

    tk.Button(botones, text="Reporte Completo", command=lambda: generar(False),
              bg="#1565C0", fg="white", activebackground="#1565C0", activeforeground="white",
              relief="flat", bd=0, font=("Segoe UI", 9, "bold"), padx=18, pady=8,
              cursor="hand2").pack(side="left", padx=(0, 10))

    tk.Button(botones, text="Solo Diferencias", command=lambda: generar(True),
              bg="#0D1B2A", fg="#64B5F6", activebackground="#0D1B2A", activeforeground="#90CAF9",
              relief="flat", bd=1, highlightbackground="#1565C0", highlightthickness=1,
              font=("Segoe UI", 9, "bold"), padx=18, pady=8, cursor="hand2").pack(side="left")
