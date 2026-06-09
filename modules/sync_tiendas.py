# modules/sync_tiendas.py
from config.utils import agregar_insert, collector
from config.db import get_connections

def generar_inserts_tiendas_faltantes():
    """
    Genera INSERTs de tiendas faltantes y exporta a TXT.
    """
    collector.clear()
    conn_sig, cur_sig, conn_web, cur_web = get_connections()
    try:
        cur_sig = conn_sig.cursor(dictionary=True)
        cur_web = conn_web.cursor(dictionary=True)

        cur_sig.execute("""
            SELECT idtienda, nombre, tipo, direccion, orden, activo,
                   principal, correo_tienda, provincia
            FROM tienda
        """)
        tiendas_sig = cur_sig.fetchall()

        cur_web.execute("SELECT id_Tienda FROM tienda")
        tiendas_web = {t['id_Tienda'] for t in cur_web.fetchall()}

        for t in tiendas_sig:
            if str(t['idtienda']).isdigit():
                id_tienda_sig = int(t['idtienda'])
                if id_tienda_sig not in tiendas_web:
                    sql = f"""INSERT INTO tienda (
                        id_Tienda, id_Anillo, id_Territorio, nombre, tipo,
                        direccion, orden, activo, principal, email, provincia
                    ) VALUES (
                        {id_tienda_sig}, 4, 16,
                        '{(t['nombre'] or '').replace("'", "''")}',
                        '{(str(t['tipo']) or '').replace("'", "''")}',
                        '{(t['direccion'] or '').replace("'", "''")}',
                        {t.get('orden', 0)},
                        {t.get('activo', 1)},
                        {t.get('principal', 0)},
                        '{(t.get('correo_tienda') or '').replace("'", "''")}',
                        '{(t.get('provincia') or '').replace("'", "''")}'
                    );"""
                    agregar_insert(sql)

        collector.export_to_file("tiendas")
        return collector.get_inserts()
    finally:
        cur_sig.close(); cur_web.close(); conn_sig.close(); conn_web.close()
