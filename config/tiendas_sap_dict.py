# config/tiendas_sap_dict.py
"""
Mapeo idtienda (SIG) → WhsCode (SAP) almacenado en SIG_DB (tabla `tienda_sap_mapping`).
Al guardar, todos los equipos ven el cambio inmediatamente.
Fallback a config/tiendas_sap_mapping.json si la BD no está disponible.
"""
import json
from pathlib import Path

_FALLBACK_PATH = Path(__file__).parent / 'tiendas_sap_mapping.json'

# Semilla inicial (lo que antes vivía hardcodeado como MAPEO_TIENDAS_SAP).
# Solo se usa para poblar la tabla la primera vez que se ejecuta cargar().
_DEFAULTS: dict[str, str] = {
    "37": "02", "45": "03", "84": "04", "87": "05", "46": "06",
    "92": "07", "53": "08", "12": "09", "83": "10", "105": "11",
    "03": "12", "05": "13", "09": "14", "14": "15", "22": "16",
    "24": "17", "25": "18", "26": "19", "27": "20", "30": "21",
    "31": "22", "34": "23", "35": "24", "36": "25", "41": "26",
    "42": "27", "43": "28", "47": "29", "48": "30", "49": "31",
    "50": "32", "52": "33", "54": "34", "55": "35", "58": "36",
    "59": "37", "60": "38", "61": "39", "62": "40", "63": "41",
    "64": "42", "65": "43", "66": "44", "67": "45", "69": "46",
    "71": "47", "72": "48", "73": "49", "74": "50", "76": "51",
    "80": "52", "81": "53", "82": "54", "85": "55", "86": "56",
    "88": "57", "89": "58", "90": "59", "91": "60", "93": "61",
    "94": "62", "95": "63", "96": "64", "97": "65", "104": "66",
    "106": "67", "99": "68",
}


def _get_conn():
    import mysql.connector
    from config.settings import SIG_DB
    return mysql.connector.connect(**SIG_DB)


def _crear_tabla(conn) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tienda_sap_mapping (
            idtienda VARCHAR(10) NOT NULL PRIMARY KEY,
            whs_code VARCHAR(10) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    cur.close()


def cargar() -> dict[str, str]:
    """Lee el mapeo desde SIG_DB. Fallback a JSON local si falla la conexión."""
    try:
        conn = _get_conn()
        _crear_tabla(conn)
        cur = conn.cursor()
        cur.execute("SELECT idtienda, whs_code FROM tienda_sap_mapping ORDER BY idtienda")
        rows = dict(cur.fetchall())
        conn.close()
        if rows:
            return rows
        # Tabla vacía en primera carga — inicializar con la semilla
        guardar(dict(_DEFAULTS))
        return dict(_DEFAULTS)
    except Exception:
        pass

    # Fallback: JSON local
    if _FALLBACK_PATH.exists():
        try:
            with open(_FALLBACK_PATH, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return dict(_DEFAULTS)


def guardar(d: dict[str, str]) -> None:
    """
    Guarda el mapeo en SIG_DB (REPLACE + DELETE de claves eliminadas).
    También escribe JSON local como caché/backup.
    """
    _guardar_json(d)  # siempre actualizar backup local primero

    try:
        conn = _get_conn()
        _crear_tabla(conn)
        cur = conn.cursor()

        if d:
            cur.executemany(
                "REPLACE INTO tienda_sap_mapping (idtienda, whs_code) VALUES (%s, %s)",
                list(d.items()),
            )
            placeholders = ','.join(['%s'] * len(d))
            cur.execute(
                f"DELETE FROM tienda_sap_mapping WHERE idtienda NOT IN ({placeholders})",
                list(d.keys()),
            )
        else:
            cur.execute("DELETE FROM tienda_sap_mapping")

        conn.commit()
        conn.close()
    except Exception:
        # Si falla la BD, el JSON local ya fue guardado arriba
        pass


def _guardar_json(d: dict[str, str]) -> None:
    try:
        with open(_FALLBACK_PATH, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        pass
