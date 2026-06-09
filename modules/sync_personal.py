from config.db import get_connections

# ==========================================
# INSERTS PERSONAL
# ==========================================
def generar_inserts_personal():
    inserts = []
    updates = []  # mantenemos consistencia

    conn_sig, cur_sig, conn_web, cur_web = get_connections()

    try:
        cur_sig = conn_sig.cursor(dictionary=True)
        cur_web = conn_web.cursor(dictionary=True)

        # 🔹 SIG
        cur_sig.execute("SELECT * FROM pl_personal")
        personal_sig = cur_sig.fetchall()

        # 🔹 WEB
        cur_web.execute("SELECT id_Personal FROM personal")
        personal_web = {p['id_Personal'] for p in cur_web.fetchall()}

        # 🔹 Generar INSERTS
        for p in personal_sig:
            codper = p.get('codper')

            if not codper or not str(codper).isdigit():
                continue

            idp = int(codper)

            if idp not in personal_web:

                nombre = (p.get('nomper') or "").replace("'", "''")
                direccion = (p.get('direccion') or "").replace("'", "''")
                correo = (p.get('correo_corporativo') or "").replace("'", "''")

                sql = f"""
INSERT INTO personal (
    id_Personal, numeroDocumento, apellidoPaterno, apellidoMaterno,
    nombre, estadoCivil, sexo, ubigeo, telefMovil, direccion,
    emailCorporativo, fechaNacimiento, estado, usuariodigitado
)
VALUES (
    {idp},
    '{p.get('nrodoc', '')}',
    '{p.get('patper', '')}',
    '{p.get('matper', '')}',
    '{nombre}',
    '{p.get('ecivil', '')}',
    '{p.get('sexper', '')}',
    '{p.get('ubigeo', '')}',
    '{p.get('celular', '')}',
    '{direccion}',
    '{correo}',
    '{p.get('fecnac', '')}',
    '{p.get('status', '')}',
    '50650'
);
"""
                inserts.append(sql)

        return inserts, updates

    finally:
        cur_sig.close()
        cur_web.close()
        conn_sig.close()
        conn_web.close()


# ==========================================
# UPDATE ESTADO PERSONAL
# ==========================================
def actualizar_estado_personal():
    inserts = []  # mantenemos consistencia
    updates = []

    conn_sig, cur_sig, conn_web, cur_web = get_connections()

    try:
        cur_sig = conn_sig.cursor(dictionary=True)
        cur_web = conn_web.cursor(dictionary=True)

        # 🔹 SIG
        cur_sig.execute("SELECT codper, status FROM pl_personal")
        pl_personal = cur_sig.fetchall()

        # 🔹 WEB
        cur_web.execute("SELECT id_Personal, estado FROM personal")
        estados_web = {r['id_Personal']: r['estado'] for r in cur_web.fetchall()}

        # 🔹 Generar UPDATES
        for p in pl_personal:
            codper = p.get('codper')

            if not codper or not str(codper).isdigit():
                continue

            idp = int(codper)
            estado_sig = p.get('status')

            if idp in estados_web and estados_web[idp] != estado_sig:

                sql = f"""
UPDATE personal
SET estado = '{estado_sig}'
WHERE id_Personal = {idp};
"""
                updates.append(sql)

        return inserts, updates

    finally:
        cur_sig.close()
        cur_web.close()
        conn_sig.close()
        conn_web.close()