from tkinter import messagebox
from controllers.sync_controller import _ejecutar_proceso

from modules import (
    validar_faltantes_personaltienda,
    validar_faltantes_formulacion,
    validar_formulacion_detalle
)


# ==========================================
# ✅ VALIDACIÓN PERSONALTIENDA (PRO)
# ==========================================
def validar_personaltienda_controller(parent, cur_web, conn_web):
    """
    - Valida faltantes de personaltienda
    - Genera TXT (antes de ejecutar)
    - Permite habilitar registros si corresponde
    - Usa flujo estándar (_ejecutar_proceso)
    """

    _ejecutar_proceso(
        parent=parent,
        nombre="VALIDAR PERSONALTIENDA",
        generar_func=validar_faltantes_personaltienda.validar_faltantes_personaltienda,
        cur=cur_web,
        conn=conn_web,
        usar_inserts=False,   # 🔥 no hay inserts
        usar_updates=True,    # 🔥 sí hay updates
        exportar=True
    )


# ==========================================
# 🟡 VALIDACIÓN FORMULACIONES (VENTANA)
# ==========================================
def abrir_validacion_formulaciones(root, obtener_tiendas_sig):
    import tkinter as tk
    from tkinter import ttk

    win = tk.Toplevel(root)
    win.title("Verificar Formulación por Tienda")
    win.geometry("600x600")

    ttk.Label(win, text="Selecciona las tiendas para validar:").pack(pady=10)

    # ===============================
    # SCROLL
    # ===============================
    contenedor = ttk.Frame(win)
    contenedor.pack(fill="both", expand=True, padx=10, pady=5)

    canvas = tk.Canvas(contenedor)
    scrollbar = ttk.Scrollbar(contenedor, orient="vertical", command=canvas.yview)
    frame_scroll = ttk.Frame(canvas)

    frame_scroll.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=frame_scroll, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # ===============================
    # TIENDAS
    # ===============================
    try:
        lista_tiendas = obtener_tiendas_sig()
    except Exception as e:
        messagebox.showerror("Error", f"No se pudieron obtener las tiendas:\n{e}")
        win.destroy()
        return

    checks = {}

    select_all_var = tk.BooleanVar()

    def toggle_all():
        for v in checks.values():
            v.set(select_all_var.get())

    ttk.Checkbutton(
        frame_scroll,
        text="Seleccionar todas",
        variable=select_all_var,
        command=toggle_all
    ).pack(anchor="w", fill="x", pady=(0, 5))

    for t_id, nombre, _ in lista_tiendas:
        var = tk.BooleanVar()
        chk = ttk.Checkbutton(frame_scroll, text=nombre, variable=var)
        chk.pack(anchor="w", fill="x")
        checks[t_id] = var

    # ===============================
    # ACCIONES
    # ===============================
    def ejecutar_validacion_faltantes():
        seleccionadas = [tid for tid, v in checks.items() if v.get()]

        if not seleccionadas:
            messagebox.showwarning("Atención", "Debes seleccionar al menos una tienda.")
            return

        try:
            ruta = validar_faltantes_formulacion.validar_faltantes_formulacion_varias(
                seleccionadas,
                nombre_archivo=None
            )

            messagebox.showinfo(
                "Validación completada",
                f"Archivo generado:\n{ruta}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error:\n{e}")

        finally:
            win.destroy()

    def ejecutar_validacion_detalle():
        seleccionadas = [tid for tid, v in checks.items() if v.get()]

        if not seleccionadas:
            messagebox.showwarning("Atención", "Debes seleccionar al menos una tienda.")
            return

        try:
            ruta = validar_formulacion_detalle.validar_formulacion_detalle_varias(
                seleccionadas
            )

            messagebox.showinfo(
                "Validación completada",
                f"Archivo generado:\n{ruta}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error:\n{e}")

        finally:
            win.destroy()

    # ===============================
    # BOTONES
    # ===============================
    frame_botones = ttk.Frame(win)
    frame_botones.pack(pady=10)

    ttk.Button(
        frame_botones,
        text="Validar Faltantes",
        command=ejecutar_validacion_faltantes
    ).grid(row=0, column=0, padx=5)

    ttk.Button(
        frame_botones,
        text="Validar Detalle",
        command=ejecutar_validacion_detalle
    ).grid(row=0, column=1, padx=5)

    ttk.Button(
        frame_botones,
        text="Cancelar",
        command=win.destroy
    ).grid(row=0, column=2, padx=5)