from config.db import get_connections


def generar_inserts_detallecargo():
    """
    Genera INSERTs de cargos faltantes en detallecargo (WEB)
    a partir del SIG.
    """

    inserts = []
    updates = []  # 🔥 importante aunque no uses
    logs = []

    conn_sig, cur_sig, conn_web, cur_web = get_connections()

    try:
        cur_sig = conn_sig.cursor(dictionary=True)
        cur_web = conn_web.cursor(dictionary=True)

        # 🔹 Cargos del SIG (maestro)
        cur_sig.execute("""
            SELECT DISTINCT 
                c.cargo*1 AS id_detalleCargo,
                m.descrip AS descripcion,
                m.orden AS orden
            FROM pl_cargos c
            INNER JOIN multitabla m 
                ON m.id_key = c.cargo AND m.id_tipo = '05'
            ORDER BY c.cargo*1
        """)
        cargos_sig = cur_sig.fetchall()

        # 🔹 Cargos existentes en WEB
        cur_web.execute("SELECT id_detalleCargo FROM detallecargo")
        cargos_web = {c['id_detalleCargo'] for c in cur_web.fetchall()}

        # 🔹 Generar INSERTS
        for c in cargos_sig:
            id_cargo = c["id_detalleCargo"]
            descripcion = (c["descripcion"] or "").strip().replace("'", "''")

            # Validación
            if not descripcion:
                logs.append(f"-- Cargo {id_cargo} sin descripción, omitido")
                continue

            orden = c["orden"] if c["orden"] is not None else 0

            if id_cargo not in cargos_web:
                inserts.append(f"""
INSERT INTO detallecargo 
(id_detalleCargo, id_cargo, nombre, orden, activo, abrev, fhactualizacion)
VALUES ({id_cargo}, 1, '{descripcion}', {orden}, 1, '{descripcion}', NOW());
""")

        return inserts, updates, logs

    finally:
        cur_sig.close()
        cur_web.close()
        conn_sig.close()
        conn_web.close()