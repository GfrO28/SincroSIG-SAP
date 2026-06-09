# gui / main_window.py

from tkinter import ttk
import ttkbootstrap as tb

from config.db import get_connections
from config.utils import obtener_tiendas_sig
from gui.progress_window import ProgressWindow
from controllers.formulaciones_controller import abrir_interfaz_formulaciones
from controllers.sync_controller import (
    sync_personal_controller,
    sync_estado_controller,
    sync_personaltienda_controller,
    sync_tiendas_controller,
    sync_detallecargo_controller,
    sync_cargos_controller
)
from controllers.validacion_controller import (
    validar_personaltienda_controller,
    abrir_validacion_formulaciones
)
from controllers.reconciliacion_controller import abrir_interfaz_reconciliacion

def run_gui():
    """
    Lanza la ventana principal de la aplicación de sincronización.
    """
    # --- Establecer conexiones una sola vez ---
    conn_sig, cur_sig, conn_web, cur_web = get_connections()

    try:
        root = tb.Window(themename="superhero")
        style = ttk.Style()
        style.configure(
            "TButton",
            font=("Segoe UI", 10, "bold"),
            padding=8
        )

        root.title("Sincronización Rustica")
        root.geometry("840x640")
        root.resizable(False, False)

        # ===============================
        # 🔵 CONTENEDOR PRINCIPAL 
        # ===============================
        frame_principal = ttk.Frame(root)
        frame_principal.pack(expand=True, fill="both", padx=10, pady=10)

        # ===============================
        # 🔵 FRAME PRINCIPAL SGCONTA
        # ===============================
        frame_sgconta = ttk.LabelFrame(frame_principal, text="SGCONTA", padding=10)
        frame_sgconta.pack(fill="both", expand=True, padx=5, pady=5)


        # ===============================
        # 🔵 PERSONAL
        # ===============================
        frame_personal_sub = ttk.LabelFrame(frame_sgconta, text="PERSONAL", padding=10)
        frame_personal_sub.pack(fill="both", expand=True, padx=5, pady=5)

        frame_personal_sub.columnconfigure(0, weight=1)
        frame_personal_sub.columnconfigure(1, weight=1)

        botones_personal = [
            ("Sincronizar PERSONAL", lambda: sync_personal_controller(root, cur_web, conn_web), "success"),
            ("Sincornizar ESTADO PERSONAL", lambda: sync_estado_controller(root, cur_web, conn_web), "warning"),
        ]

        for idx, (texto, comando, estilo) in enumerate(botones_personal):
            btn = tb.Button(
                frame_personal_sub,
                text=texto,
                command=comando,
                bootstyle=estilo,
                width=25
            )
            btn.grid(row=0, column=idx, padx=8, pady=8, sticky="nsew")


        # ===============================
        # 🟡 TIENDAS
        # ===============================
        frame_tiendas_sub = ttk.LabelFrame(frame_sgconta, text="TIENDAS", padding=10)
        frame_tiendas_sub.pack(fill="both", expand=True, padx=5, pady=5)

        frame_tiendas_sub.columnconfigure(0, weight=1)
        frame_tiendas_sub.columnconfigure(1, weight=1)
        frame_tiendas_sub.columnconfigure(2, weight=1)

        botones_tiendas = [
            ("Sincronizar TIENDAS", lambda: sync_tiendas_controller(root, cur_web, conn_web), "primary"),
            ("Sincronizar TIENDA PERSONAL", lambda: sync_personaltienda_controller(root, cur_web, conn_web), "info"),
            ("Verificar PERSONALTIENDAS", lambda: validar_personaltienda_controller(root, cur_web, conn_web), "dark"),
        ]

        for idx, (texto, comando, estilo) in enumerate(botones_tiendas):
            btn = tb.Button(
                frame_tiendas_sub,
                text=texto,
                command=comando,
                bootstyle=estilo,
                width=25
            )
            btn.grid(row=0, column=idx, padx=8, pady=8, sticky="nsew")


        # ===============================
        # 🔴 CARGOS
        # ===============================
        frame_cargos_sub = ttk.LabelFrame(frame_sgconta, text="CARGOS", padding=10)
        frame_cargos_sub.pack(fill="both", expand=True, padx=5, pady=5)

        frame_cargos_sub.columnconfigure(0, weight=1)
        frame_cargos_sub.columnconfigure(1, weight=1)
        frame_cargos_sub.columnconfigure(2, weight=1)
        frame_cargos_sub.columnconfigure(3, weight=1)

        botones_cargos = [
            ("Sincronizar DETALLE CARGO", lambda: sync_detallecargo_controller(root, cur_web, conn_web), "dark"),
            ("Sincronizar CARGO PERSONAL", lambda: sync_cargos_controller(root, cur_web, conn_web), "primary"),
        ]

        for idx, (texto, comando, estilo) in enumerate(botones_cargos):
            btn = tb.Button(
                frame_cargos_sub,
                text=texto,
                command=comando,
                bootstyle=estilo,
                width=25
            )
            btn.grid(row=0, column=idx, padx=8, pady=8, sticky="nsew")

        # ===============================
        # 🟢 FRAME FORMULACIONES
        # ===============================
        frame_formulaciones = ttk.LabelFrame(frame_principal, text="FORMULACIONES", padding=10)
        frame_formulaciones.pack(fill="both", expand=True, padx=5, pady=5)

        for i in range(2):
            frame_formulaciones.columnconfigure(i, weight=1)

        botones_formulaciones = [
            ("Verificar Formulación TDA vs SIG", lambda: abrir_validacion_formulaciones(root, obtener_tiendas_sig), "dark"),
            ("Reporte Comparativo de Formulaciones", lambda: abrir_interfaz_formulaciones(root, obtener_tiendas_sig), "success"),
        ]

        for idx, (texto, comando, estilo) in enumerate(botones_formulaciones):
            btn = tb.Button(
                frame_formulaciones,
                text=texto,
                command=comando,
                bootstyle=estilo,
                width=30
            )
            btn.grid(row=0, column=idx, padx=10, pady=10, sticky="nsew")

        # ===============================
        # 📦 FRAME INVENTARIOS SAP (NUEVO)
        # ===============================
        frame_sap_ajustes = ttk.LabelFrame(frame_principal, text="AJUSTES SAP", padding=10)
        frame_sap_ajustes.pack(fill="both", expand=True, padx=5, pady=5)

        btn_reconcilia = tb.Button(
            frame_sap_ajustes, 
            text="Reconciliación de Stock", 
            command=lambda: abrir_interfaz_reconciliacion(root),
            bootstyle="warning",
            width=40
        )
        btn_reconcilia.pack(pady=10)

        # ===============================
        # 🔴 BOTÓN SALIR
        # ===============================
        btn_salir = tb.Button(
            root,
            text="Salir",
            command=root.destroy,
            bootstyle="danger",
            width=30
        )
        btn_salir.pack(pady=10)

        root.mainloop()

    finally:
        # --- Cierre seguro de conexiones ---
        try:
            cur_sig.close()
            cur_web.close()
            conn_sig.close()
            conn_web.close()
        except Exception:
            pass