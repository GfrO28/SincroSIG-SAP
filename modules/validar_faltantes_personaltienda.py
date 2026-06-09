# modules/validar_faltantes_personaltienda.py
from datetime import datetime
from config.db import get_connections


def validar_faltantes_personaltienda():
    """
    Verifica qué códigos existen en SIG pero no tienen registro habilitado en WEB.
    """

    inserts = []   # 🔥 no usado pero consistente
    updates = []
    logs = []

    conn_sig, cur_sig, conn_web, cur_web = get_connections()

    try:
        cur_sig = conn_sig.cursor(dictionary=True)
        cur_web = conn_web.cursor(dictionary=True)

        # ==========================================
        # 🔹 SIG: último registro por persona
        # ==========================================
        cur_sig.execute("""
            SELECT t1.codper AS id_Personal,
                   t1.tienda AS id_Tienda,
                   t1.digitado AS fecha_sig
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
        """)
        sig_rows = cur_sig.fetchall()
        sig_ids = {int(r["id_Personal"]) for r in sig_rows}

        # ==========================================
        # 🔹 WEB habilitados
        # ==========================================
        cur_web.execute("""
            SELECT DISTINCT id_Personal
            FROM personaltienda
            WHERE habilitado = 1
        """)
        web_ids = {int(r["id_Personal"]) for r in cur_web.fetchall()}

        # ==========================================
        # 🔹 FALTANTES
        # ==========================================
        faltantes = sorted(sig_ids - web_ids)

        for cod in faltantes:
            logs.append(f"-- FALTANTE: {cod}")

        # ==========================================
        # 🔹 BUSCAR POSIBLES REHABILITACIONES
        # ==========================================
        if faltantes:
            format_ids = ",".join(str(i) for i in faltantes)

            cur_web.execute(f"""
                SELECT id_Personal, id_Tienda, DATE(fechadigitado) AS fecha_web
                FROM personaltienda
                WHERE habilitado = 0
                  AND id_Personal IN ({format_ids})
            """)
            web_rows = cur_web.fetchall()

            for s in sig_rows:
                pid = int(s["id_Personal"])
                if pid not in faltantes:
                    continue

                tda = int(s["id_Tienda"])
                fecha_sig = s["fecha_sig"]

                if isinstance(fecha_sig, datetime):
                    fecha_sig_d = fecha_sig.date()
                else:
                    fecha_sig_d = datetime.strptime(
                        str(fecha_sig)[:10], "%Y-%m-%d"
                    ).date()

                for w in web_rows:
                    if (
                        int(w["id_Personal"]) == pid and
                        int(w["id_Tienda"]) == tda and
                        w["fecha_web"] == fecha_sig_d
                    ):
                        updates.append(f"""
UPDATE personaltienda
SET habilitado = 1
WHERE id_Personal = {pid}
  AND id_Tienda = {tda}
  AND DATE(fechadigitado) = '{fecha_sig_d}'
  AND habilitado = 0;
""")
                        break

        print(f"Total faltantes: {len(faltantes)}")

        return inserts, updates, logs

    finally:
        cur_sig.close()
        cur_web.close()
        conn_sig.close()
        conn_web.close()