# modules/sync_personaltienda.py
from config.db import get_connections


def sync_personaltienda():
    """
    Sincroniza personaltienda en WEB desde SIG en dos pasos:

    Paso 1: Insertar siempre que en SIG haya una tienda/fecha que no exista
    Paso 2: Deshabilitar registros incorrectos
    """

    inserts = []
    updates = []

    conn_sig, cur_sig, conn_web, cur_web = get_connections()

    try:
        cur_sig = conn_sig.cursor(dictionary=True)
        cur_web = conn_web.cursor(dictionary=True)

        # ==========================================
        # 🔹 SIG: último registro por persona
        # ==========================================
        cur_sig.execute("""
            SELECT t1.codper  AS id_Personal,
                   t1.tienda AS id_Tienda,
                   t1.digitado AS fechadigitado,
                   50650      AS usuariodigitado,
                   t1.fecha   AS fecha,
                   t1.observacion
            FROM pl_tiendas t1
            INNER JOIN (
                SELECT codper, MAX(digitado) AS max_dig
                FROM pl_tiendas
                GROUP BY codper
            ) t2 ON t1.codper = t2.codper AND t1.digitado = t2.max_dig
            WHERE t1.codper <> ''
              AND t1.codper <> '1'
              AND t1.tienda IS NOT NULL
              AND t1.tienda <> ''
            ORDER BY t1.codper;
        """)
        sig_rows = cur_sig.fetchall()

        # ==========================================
        # 🔹 WEB: registros habilitados
        # ==========================================
        cur_web.execute("""
            SELECT id_Personal, id_Tienda, fechadigitado, habilitado
            FROM personaltienda
            WHERE habilitado = 1
        """)

        web_by_person = {}
        for r in cur_web.fetchall():
            pid = int(r["id_Personal"])
            web_by_person.setdefault(pid, []).append({
                "id_Tienda": int(r["id_Tienda"]),
                "fechadigitado": r["fechadigitado"],
                "habilitado": int(r["habilitado"])
            })

        # ==========================================
        # 🔹 PASO 1: INSERTAR SI NO EXISTE
        # ==========================================
        for t in sig_rows:
            pid = int(t["id_Personal"])
            tda = int(t["id_Tienda"])
            fch = t["fechadigitado"]

            rows = web_by_person.get(pid, [])

            existe_misma_tienda = any(
                r["id_Tienda"] == tda
                for r in rows
            )

            if not existe_misma_tienda:
                inserts.append(f"""
INSERT INTO personaltienda (
    id_Personal, id_Tienda, fechadigitado,
    usuariodigitado, fecha, habilitado, observacion
) VALUES (
    {pid}, {tda}, '{fch}',
    {t['usuariodigitado']}, '{t['fecha']}', 1,
    '{(t['observacion'] or '').replace("'", "''")}'
);
""")

        # ==========================================
        # 🔹 PASO 2: DESHABILITAR INCORRECTOS
        # ==========================================
        for t in sig_rows:
            pid = int(t["id_Personal"])
            tda = int(t["id_Tienda"])
            fch = t["fechadigitado"]

            rows = web_by_person.get(pid, [])

            for r in rows:
                if (
                    r["habilitado"] == 1 and
                    (r["id_Tienda"] != tda or str(r["fechadigitado"]) < str(fch))
                ):
                    updates.append(f"""
UPDATE personaltienda
SET habilitado = 0
WHERE id_Personal   = {pid}
  AND id_Tienda     = {r['id_Tienda']}
  AND fechadigitado = '{r['fechadigitado']}'
  AND habilitado    = 1;
""")

        return inserts, updates

    finally:
        cur_sig.close()
        cur_web.close()
        conn_sig.close()
        conn_web.close()