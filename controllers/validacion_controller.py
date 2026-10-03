from controllers.sync_controller import _ejecutar_proceso

from modules import validar_faltantes_personaltienda


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
