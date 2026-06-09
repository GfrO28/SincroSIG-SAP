# controllers/formulaciones_controller.py

import tkinter as tk
import threading
import os
from tkinter import messagebox
from gui.searchable_checklist import SearchableCheckList
from config.db import get_connections, get_store_connection
from config.utils import cargar_cache, guardar_cache
from modules import filtro_insumos
from modules.formulaciones_engine import construir_dataset_formulaciones
from modules.formulaciones_export import exportar_excel_dataset
from gui.progress_window import ProgressWindow
from modules.preciart_service import articulo_valido_para_formulacion
from modules.formulaciones_service import (
    obtener_formulas_por_insumos,
    obtener_formulaciones_sig,
    obtener_idformulacion_batch_multi,
    obtener_detalles_formulaciones_batch,
    obtener_detalle_formulacion,
)

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
def abrir_interfaz_formulaciones(root, obtener_tiendas_sig):

    win = tk.Toplevel(root)
    win.title("Seleccionar Tiendas y Formulaciones")
    win.geometry("900x600")

    lbl_estado = tk.Label(win, text="Cargando datos, por favor espere...")
    lbl_estado.pack(pady=20)

    frame_principal = tk.Frame(win)
    frame_principal.pack(fill="both", expand=True)
    frame_principal.pack_forget()

    # ==========================================
    # CREAR LISTA GENERICA
    # ==========================================
    def crear_lista(parent, titulo):
        frame = tk.LabelFrame(parent, text=titulo)
        frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        frame_top = tk.Frame(frame)
        frame_top.pack(fill="x", pady=5)

        frame_content = tk.Frame(frame)
        frame_content.pack(fill="both", expand=True)

        return frame_top, frame_content

    # ==========================================
    # CARGA DE DATOS EN BACKGROUND
    # ==========================================
    def cargar_datos():
        try:
            tiendas = cargar_cache("tiendas")
            formulas = cargar_cache("formulas")

            if not tiendas or not formulas:
                tiendas = obtener_tiendas_sig()
                formulas = obtener_formulaciones_sig()
                guardar_cache("tiendas", tiendas)
                guardar_cache("formulas", formulas)

        except Exception as e:
            win.after(0, lambda: messagebox.showerror("Error", str(e)))
            win.after(0, win.destroy)
            return

        win.after(0, lambda: mostrar_listas(tiendas, formulas))

    # ==========================================
    # UI PRINCIPAL
    # ==========================================
    def mostrar_listas(tiendas, formulas):

        lbl_estado.pack_forget()
        frame_principal.pack(fill="both", expand=True)

        frame_t_top, frame_t_content = crear_lista(frame_principal, "Tiendas")
        frame_f_top, frame_f_content = crear_lista(frame_principal, "Formulaciones")

        # ======================================
        # TIENDAS
        # ======================================
        lista_tiendas = SearchableCheckList(
            frame_t_content,
            [(idtienda, nombre) for idtienda, nombre, _ in tiendas]
        )

        tipos_tienda = {idtienda: tipo for idtienda, _, tipo in tiendas}

        def filtrar_tipo(tipo):
            ids = [tid for tid, t in tipos_tienda.items() if t == tipo]
            lista_tiendas.set_checked(ids)

        tk.Button(frame_t_top, text="Hoteles", command=lambda: filtrar_tipo(3)).pack(side="left")
        tk.Button(frame_t_top, text="Lima", command=lambda: filtrar_tipo(1)).pack(side="left")
        tk.Button(frame_t_top, text="Provincia", command=lambda: filtrar_tipo(2)).pack(side="left")

        # ======================================
        # FORMULACIONES
        # ======================================
        lista_formulas = SearchableCheckList(
            frame_f_content,
            [(idart, f"{idart} - {desc}") for idart, desc in formulas]
        )

        # reset filtro
        btn_reset = tk.Button(frame_f_top, text="Quitar filtro", state="disabled")
        btn_reset.pack(side="left", padx=5)

        def filtrar_por_insumo():
            seleccion = filtro_insumos.seleccionar_insumo(win)
            if not seleccion:
                return

            id_insumo, _ = seleccion

            conn_sig, cur_sig, _, _ = get_connections()
            validas = obtener_formulas_por_insumos(cur_sig, [id_insumo])

            nuevas = [
                (idart, f"{idart} - {desc}")
                for idart, desc in formulas
                if idart in validas
            ]

            lista_formulas.set_items(nuevas)
            btn_reset.config(state="normal")

        def reset_filtro():
            lista_formulas.set_items([
                (idart, f"{idart} - {desc}") for idart, desc in formulas
            ])
            btn_reset.config(state="disabled")

        tk.Button(
            frame_f_top,
            text="Filtrar por insumo",
            command=filtrar_por_insumo
        ).pack(side="left")

        btn_reset.config(command=reset_filtro)

        def manejar_error(progress, err):
            progress.close()
            messagebox.showerror("Error", str(err))

        # ==========================================
        # GENERAR REPORTE (PRO MODE)
        # ==========================================
        def generar(solo_diferencias=False):

            tdas = lista_tiendas.get_selected()
            forms = list(map(int, lista_formulas.get_selected()))

            if not tdas:
                messagebox.showwarning("Aviso", "Seleccione al menos una tienda")
                return

            if not forms:
                messagebox.showwarning("Aviso", "Seleccione al menos una formulación")
                return

            progress = ProgressWindow(root, "Generando reporte...")

            def tarea():
                conn_sig = None
                cur_val = None
                print("1 - conexiones OK (inicio tarea)")
                try:
                    # ==========================================
                    # 🔵 CONEXIONES
                    # ==========================================
                    conn_sig, cur_val, _, _ = get_connections()
                    print("1 - conexiones OK")

                    # ==========================================
                    # 🔵 METADATA (tipo de tienda)
                    # ==========================================
                    tiendas_info = obtener_tiendas_sig()
                    tipo_por_tienda = {
                        int(t[0]): int(t[2]) for t in tiendas_info
                    }
                    print("2 - cache OK")

                    # ==========================================
                    # 🔵 BASES FIJAS
                    # ==========================================
                    base_por_tipo = {1: 3, 2: 34, 3: 41}

                    # ==========================================
                    # 🔵 CACHE ID FORMULACIONES (OPTIMIZADO)
                    # ==========================================
                    cache_idforms = {}

                    try:
                        cache_idforms = obtener_idformulacion_batch_multi(
                            cur_val,
                            tdas,
                            forms
                        )

                    except Exception as e:
                        print("ERROR CACHE IDFORMS:", e)
                        cache_idforms = {}

                    # ==========================================
                    # 🔵 CACHE DETALLES
                    # ==========================================
                    cache_detalles = {}

                    if cache_idforms:
                        try:
                            cache_detalles = obtener_detalles_formulaciones_batch(
                                cur_val,
                                list(cache_idforms.values())
                            )
                        except Exception:
                            cache_detalles = {}

                    # ==========================================
                    # 🔵 ENGINE → DATASET
                    # ==========================================
                    print("3 - engine start")
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

                    # ==========================================
                    # 🔴 EXPORT → EXCEL
                    # ==========================================
                    print(dataset.keys())
                    print(len(dataset["articulos"]))
                    print("4 - export start")
                    ruta = exportar_excel_dataset(
                        dataset=dataset,
                        tiendas=tdas,                        
                        solo_diferencias=solo_diferencias,
                        base_por_tipo=base_por_tipo,
                    )
                    # ==========================================
                    # VALIDACIÓN ROBUSTA
                    # ==========================================
                    if not dataset:
                        raise Exception("Dataset vacío: no se generó ninguna data")

                    if not isinstance(dataset, dict):
                        raise Exception(f"Formato inválido del dataset: {type(dataset)}")

                    if not dataset.get("articulos"):
                        raise Exception("Dataset vacío: no se generó ninguna formulación")

                    print(f"DEBUG: articulos generados = {len(dataset['articulos'])}")

                    print("5 - export end")
                    print("ruta:", ruta)
                    if not ruta or not os.path.exists(ruta):
                        raise Exception("El Excel no se generó correctamente")

                    # ==========================================
                    # 🔵 FINALIZAR UI
                    # ==========================================
                    def finalizar():
                        progress.close()
                        messagebox.showinfo("Éxito", f"Reporte generado:\n{ruta}")

                    progress.top.after(0, finalizar)

                except Exception as e:
                    import traceback
                    err = traceback.format_exc()
                    print(err)

                    def error_ui():
                        progress.close()
                        messagebox.showerror("Error", err)  # 👈 mostrar traceback completo

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

        # ==========================================
        # BOTONES PRO
        # ==========================================
        frame_botones = tk.Frame(win)
        frame_botones.pack(pady=10)

        tk.Button(
            frame_botones,
            text="Reporte Completo",
            command=lambda: generar(False),
            width=20
        ).grid(row=0, column=0, padx=5)

        tk.Button(
            frame_botones,
            text="Solo Diferencias",
            command=lambda: generar(True),
            width=20
        ).grid(row=0, column=1, padx=5)

        tk.Button(
            frame_botones,
            text="Cancelar",
            command=win.destroy,
            width=20
        ).grid(row=0, column=2, padx=5)

    # ==========================================
    # THREAD INICIAL
    # ==========================================
    threading.Thread(target=cargar_datos, daemon=True).start()