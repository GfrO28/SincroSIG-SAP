import threading
from tkinter import messagebox
from gui.progress_window import ProgressWindow
from config.utils import ejecutar_sql, export_sql_to_file

from modules import (
    sync_personal,
    sync_personaltienda,
    sync_tiendas,
    sync_personal_detallecargo,
    sync_detallecargo
)


# ==========================================
# FUNCION BASE (REUTILIZABLE)
# ==========================================

def _ejecutar_proceso(
    parent,
    nombre,
    generar_func,
    cur,
    conn,
    usar_inserts=True,
    usar_updates=True,
    mensaje_ok=None,
    exportar=True
):
    progress = ProgressWindow(parent, f"Procesando {nombre}...")

    def tarea():
        try:
            # ==========================================
            # 1. Ejecutar módulo
            # ==========================================
            progress.update(10, "Obteniendo datos...")

            resultado = generar_func()

            # ==========================================
            # 2. Normalizar resultado
            # ==========================================
            inserts = []
            updates = []
            logs = []

            if isinstance(resultado, tuple):
                inserts = resultado[0] if len(resultado) > 0 else []
                updates = resultado[1] if len(resultado) > 1 else []
                logs = resultado[2] if len(resultado) > 2 else []

            elif isinstance(resultado, dict):
                inserts = resultado.get("inserts", [])
                updates = resultado.get("updates", [])
                logs = resultado.get("logs", [])

            else:
                inserts = resultado or []

            total = len(inserts) + len(updates)

            # ==========================================
            # 3. Validación
            # ==========================================
            if total == 0:
                progress.close()
                parent.after(0, lambda: messagebox.showinfo(
                    "Sincronización",
                    f"{nombre} sincronizado al 100%. No hay registros pendientes."
                ))
                return

            # ==========================================
            # 4. Construir SQL
            # ==========================================
            sql = []
            if usar_inserts:
                sql += inserts
            if usar_updates:
                sql += updates

            # ==========================================
            # 5. EXPORTAR ANTES (🔥 TU LÓGICA)
            # ==========================================
            progress.update(30, "Generando archivo...")

            ruta = ""
            if exportar:
                contenido_export = sql + logs
                ruta = export_sql_to_file(nombre, contenido_export)

            # ==========================================
            # 6. Confirmación (EN MAIN THREAD)
            # ==========================================
            def confirmar():
                mensaje_confirmacion = f"Se generaron {total} cambios en {nombre}."

                if ruta:
                    mensaje_confirmacion += f"\n\nArchivo generado:\n{ruta}"

                mensaje_confirmacion += "\n\n¿Deseas ejecutar los cambios?"

                if not messagebox.askyesno("Confirmar", mensaje_confirmacion):
                    progress.close()
                    return

                ejecutar()

            # ==========================================
            # 7. Ejecutar SQL (CON PROGRESO REAL 🔥)
            # ==========================================
            def ejecutar():
                progress.update(50, "Ejecutando SQL...")

                def callback(porcentaje, texto):
                    progress.update(50 + porcentaje * 0.5, f"Ejecutando {texto}")

                ejecutar_sql(
                    cur,
                    conn,
                    sql,
                    nombre,
                    progress_callback=callback
                )

                progress.update(100, "Finalizado")
                progress.close()

                mensaje = mensaje_ok or f"{nombre} completado correctamente."
                messagebox.showinfo("Éxito", mensaje)

            # 🔥 volver al hilo principal
            progress.top.after(0, confirmar)

        except Exception as e:
            progress.close()
            _msg = str(e)
            parent.after(0, lambda m=_msg: messagebox.showerror("Error", m))

    # 🔥 hilo secundario (clave para no congelar UI)
    threading.Thread(target=tarea, daemon=True).start()

# ==========================================
# CONTROLADORES DE SINCRONIZACIÓN
# ==========================================

def sync_personal_controller(parent,cur_web, conn_web):
    _ejecutar_proceso(
        parent=parent,
        nombre="PERSONAL",
        generar_func=sync_personal.generar_inserts_personal,
        cur=cur_web,
        conn=conn_web,
        usar_inserts=True,
        usar_updates=True,
        exportar=True
    )


def sync_estado_controller(parent, cur_web, conn_web):
    _ejecutar_proceso(
        parent=parent,
        nombre="ESTADO PERSONAL",
        generar_func=sync_personal.actualizar_estado_personal,
        cur=cur_web,
        conn=conn_web,
        usar_inserts=False,
        usar_updates=True,
        exportar=True
    )


def sync_personaltienda_controller(parent, cur_web, conn_web):
    _ejecutar_proceso(
        parent=parent,
        nombre="PERSONALTIENDA",
        generar_func=sync_personaltienda.sync_personaltienda,
        cur=cur_web,
        conn=conn_web,
        usar_inserts=True,
        usar_updates=True,
        exportar=True
    )


def sync_tiendas_controller(parent, cur_web, conn_web):
    _ejecutar_proceso(
        parent=parent,
        nombre="TIENDAS",
        generar_func=sync_tiendas.generar_inserts_tiendas_faltantes,
        cur=cur_web,
        conn=conn_web,
        usar_inserts=True,
        usar_updates=False,
        exportar=True
    )


def sync_detallecargo_controller(parent, cur_web, conn_web):
    _ejecutar_proceso(
        parent=parent,
        nombre="DETALLE CARGO",
        generar_func=sync_detallecargo.generar_inserts_detallecargo,
        cur=cur_web,
        conn=conn_web,
        usar_inserts=True,
        usar_updates=False,
        exportar=True
    )

def sync_cargos_controller(parent, cur_web, conn_web):
    _ejecutar_proceso(
        parent=parent,
        nombre="CARGOS",
        generar_func=sync_personal_detallecargo.sync_personal_detallecargo,
        cur=cur_web,
        conn=conn_web
    )