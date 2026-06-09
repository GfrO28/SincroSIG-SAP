# modules/sync_personal_detallecargo.py

from config.db import get_connections


# ==========================================
# 1. OBTENER DATA SIG
# ==========================================
def _obtener_cargos_sig(conn_sig):
    cursor = conn_sig.cursor()

    cursor.execute("""
        SELECT
        c.codper AS CODIGO,
        c.cargo*1 AS CARGO,
        c.digitado AS FECHA_DIGITADO
        FROM pl_cargos c
        INNER JOIN (
            SELECT codper, MAX(fecha) AS max_fecha
            FROM pl_cargos
            GROUP BY codper
        ) ult
        ON ult.codper = c.codper
        AND ult.max_fecha = c.fecha
        INNER JOIN pl_personal pp 
        ON pp.codper = c.codper
        WHERE pp.status <> 'A'
        ORDER BY c.codper*1;
    """)

    data = {}

    for idp, cargo, fecha in cursor.fetchall():
        if idp is None or cargo is None or fecha is None:
            continue

        data[int(idp)] = {
            "cargo": int(cargo),
            "fecha": fecha
        }

    return data


# ==========================================
# 2. OBTENER DATA WEB
# ==========================================
def _obtener_cargos_web(conn_web):
    cursor = conn_web.cursor()

    cursor.execute("""
        SELECT 
            id_Personal,
            id_detalleCargo,
            fechaDigitado,
            estado
        FROM personaldetallecargo
        WHERE id_Personal IN (
            SELECT id_Personal 
            FROM personal 
            WHERE id_personal <> 0 
              AND id_Personal < 99999
        )
        ORDER BY id_Personal * 1;
    """)

    data = {}

    for idp, cargo, fecha, estado in cursor.fetchall():
        if idp is None or cargo is None or fecha is None:
            continue

        idp = int(idp)

        if idp not in data:
            data[idp] = []

        data[idp].append({
            "cargo": int(cargo),
            "fecha": fecha,
            "estado": int(estado) if estado is not None else 0
        })

    return data


# ==========================================
# 3. GENERAR SENTENCIAS
# ==========================================
def _generar_sentencias(sig, web):
    inserts = []
    updates = []

    for cod, datos_sig in sig.items():
        cargo_sig = datos_sig["cargo"]
        fecha_sig = datos_sig["fecha"]
        fecha_sig_str = fecha_sig.strftime("%Y-%m-%d %H:%M:%S")

        registros_web = web.get(cod, [])

        mismos_evento = [
            r for r in registros_web
            if r["fecha"].strftime("%Y-%m-%d %H:%M:%S") == fecha_sig_str
        ]

        exacto = [r for r in mismos_evento if r["cargo"] == cargo_sig]
        exacto_activo = [r for r in exacto if r["estado"] == 1]
        exacto_inactivo = [r for r in exacto if r["estado"] == 0]
        activos = [r for r in registros_web if r["estado"] == 1]

        # CASO 1
        if exacto_activo:
            for r in activos:
                if r["cargo"] != cargo_sig:
                    fecha_web = r["fecha"].strftime("%Y-%m-%d %H:%M:%S")
                    updates.append(f"""
UPDATE personaldetallecargo
SET estado = 0, usuarioDigitado = 50650
WHERE id_Personal = {cod}
AND id_detalleCargo = {r["cargo"]}
AND fechaDigitado = '{fecha_web}'
AND estado = 1;
""")
            continue

        # CASO 2
        if exacto_inactivo:
            correcto = exacto_inactivo[0]
            fecha_correcto = correcto["fecha"].strftime("%Y-%m-%d %H:%M:%S")

            for r in activos:
                if r["cargo"] != cargo_sig:
                    fecha_web = r["fecha"].strftime("%Y-%m-%d %H:%M:%S")
                    updates.append(f"""
UPDATE personaldetallecargo
SET estado = 0, usuarioDigitado = 50650
WHERE id_Personal = {cod}
AND id_detalleCargo = {r["cargo"]}
AND fechaDigitado = '{fecha_web}'
AND estado = 1;
""")

            updates.append(f"""
UPDATE personaldetallecargo
SET estado = 1, usuarioDigitado = 50650, fecha = DATE(NOW())
WHERE id_Personal = {cod}
AND id_detalleCargo = {cargo_sig}
AND fechaDigitado = '{fecha_correcto}';
""")
            continue

        # CASO 3
        if mismos_evento:
            for r in mismos_evento:
                if r["estado"] == 1:
                    fecha_web = r["fecha"].strftime("%Y-%m-%d %H:%M:%S")
                    updates.append(f"""
UPDATE personaldetallecargo
SET estado = 0, usuarioDigitado = 50650
WHERE id_Personal = {cod}
AND id_detalleCargo = {r["cargo"]}
AND fechaDigitado = '{fecha_web}'
AND estado = 1;
""")

            inserts.append(f"""
INSERT INTO personaldetallecargo 
(id_Personal, id_detalleCargo, fechaDigitado, usuarioDigitado, fecha, estado)
VALUES ({cod}, {cargo_sig}, '{fecha_sig_str}', 50650, DATE(NOW()), 1);
""")
            continue

        # CASO 4
        for r in activos:
            fecha_web = r["fecha"].strftime("%Y-%m-%d %H:%M:%S")
            updates.append(f"""
UPDATE personaldetallecargo
SET estado = 0, usuarioDigitado = 50650
WHERE id_Personal = {cod}
AND id_detalleCargo = {r["cargo"]}
AND fechaDigitado = '{fecha_web}'
AND estado = 1;
""")

        inserts.append(f"""
INSERT INTO personaldetallecargo 
(id_Personal, id_detalleCargo, fechaDigitado, usuarioDigitado, fecha, estado)
VALUES ({cod}, {cargo_sig}, '{fecha_sig_str}', 50650, DATE(NOW()), 1);
""")

    return inserts, updates


# ==========================================
# 4. FUNCIÓN PRINCIPAL (ESTÁNDAR)
# ==========================================
def sync_personal_detallecargo():
    conn_sig, cur_sig, conn_web, cur_web = get_connections()

    inserts = []
    updates = []
    logs = []

    try:
        print("🔍 Obteniendo datos SIG...")
        sig = _obtener_cargos_sig(conn_sig)

        print("🔍 Obteniendo datos WEB...")
        web = _obtener_cargos_web(conn_web)

        inserts, updates = _generar_sentencias(sig, web)

        return inserts, updates, logs  # 🔥 estándar completo

    finally:
        cur_sig.close()
        cur_web.close()
        conn_sig.close()
        conn_web.close()