# config/uom_dict.py
"""
Diccionario SAP UOM → SIG UOM almacenado en SIG_DB (tabla `uom_mapping`).
Al guardar, todos los equipos ven el cambio inmediatamente.
Fallback a config/uom_mapping.json si la BD no está disponible.
"""
import json
from pathlib import Path

_FALLBACK_PATH = Path(__file__).parent / 'uom_mapping.json'

_DEFAULTS: dict[str, str] = {
    # ── Peso ──────────────────────────────────────────────────────────────────
    "KG":              "KG",          # SAP código KG / descripción KILOGRAMOS
    "KILOGRAMO":       "KG",
    "KILOGRAMOS":      "KG",
    "GRAMO":           "GR",
    "GRAMOS":          "GR",
    "LIBRA":           "LB",
    "LIBRAS":          "LB",
    "OZ":              "OZ",          # SAP código OZ / descripción ONZA
    "ONZA":            "OZ",
    # ── Volumen ───────────────────────────────────────────────────────────────
    "LT":              "LT",          # SAP código LT
    "LITRO":           "LT",
    "LITROS":          "LT",
    "GALON":           "GALON",
    "BIDON":           "BIDON",
    "BALDE":           "BALDE",
    "BALON":           "BALON",
    "BOTELLA":         "BOTELLA",
    "FRASCO":          "FRASCO",
    "TARRO":           "TARRO",
    "VASO":            "VASO",
    "COPA":            "COPA",
    # ── Longitud / área ───────────────────────────────────────────────────────
    "METRO":           "MT",
    "METROS":          "MT",
    "MT":              "MT",
    "LAMINA":          "LAMINA",
    "ROLLO":           "ROLLO",
    # ── Unidad contable ───────────────────────────────────────────────────────
    "UNIDAD":          "UND",
    "UNIDADES":        "UND",
    "UND":             "UND",
    "PIEZA":           "PZA",
    "PIEZAS":          "PZA",
    "PAR":             "PAR",
    "PORCION":         "PORCION",
    "MANO":            "MANO",
    "ATADO":           "ATADO",
    # ── Empaque / contenedor ──────────────────────────────────────────────────
    "CAJA":            "CJA",
    "CAJAS":           "CJA",
    "CJA":             "CJA",
    "PAQUETE":         "PQ",
    "PAQUETES":        "PQ",
    "PQ":              "PQ",
    "BULTO":           "BTO",
    "BULTOS":          "BTO",
    "SACO":            "SACO",
    "BOLSA":           "BOLSA",
    "BOLSA (400GR)":   "BOLSA (400GR)",
    "SOBRE":           "SOBRE",
    "SACHET":          "SACHET",
    "EMPAQUE":         "EMPAQUE",
    "EMPAQUE (200GR)": "EMPAQUE (200GR)",
    "TAPER":           "TAPER",
    "LATA":            "LATA",
    # ── Conteo ────────────────────────────────────────────────────────────────
    "DOCENA":          "DOC",
    "DOCENAS":         "DOC",
    "DOC":             "DOC",
    "CIENTO":          "CIENTO",
    "1/2 CENTENA":     "1/2 CENTENA",
    "MILLAR":          "MILLAR",
    "RESMA":           "RESMA",
    "TALONARIO":       "TALONARIO",
    "TIRA X 24":       "TIRA X 24",
    # ── Otros ─────────────────────────────────────────────────────────────────
    "MOLDE":           "MOLDE",
    "MANUAL":          "MANUAL",
}


def _get_conn():
    import mysql.connector
    from config.settings import SIG_DB
    return mysql.connector.connect(**SIG_DB)


def _crear_tabla(conn) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS uom_mapping (
            sap_uom VARCHAR(60) NOT NULL PRIMARY KEY,
            sig_uom VARCHAR(60) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    cur.close()


def cargar() -> dict[str, str]:
    """Lee el diccionario desde SIG_DB. Fallback a JSON local si falla la conexión."""
    try:
        conn = _get_conn()
        _crear_tabla(conn)
        cur = conn.cursor()
        cur.execute("SELECT sap_uom, sig_uom FROM uom_mapping ORDER BY sap_uom")
        rows = dict(cur.fetchall())
        conn.close()
        if rows:
            return rows
        # Tabla vacía en primera carga — inicializar con defaults
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
    Guarda el diccionario en SIG_DB (REPLACE + DELETE de claves eliminadas).
    También escribe JSON local como caché/backup.
    """
    _guardar_json(d)  # siempre actualizar backup local primero

    try:
        conn = _get_conn()
        _crear_tabla(conn)
        cur = conn.cursor()

        # Upsert de todas las entradas actuales
        if d:
            cur.executemany(
                "REPLACE INTO uom_mapping (sap_uom, sig_uom) VALUES (%s, %s)",
                list(d.items()),
            )
            # Eliminar claves que el usuario borró
            placeholders = ','.join(['%s'] * len(d))
            cur.execute(
                f"DELETE FROM uom_mapping WHERE sap_uom NOT IN ({placeholders})",
                list(d.keys()),
            )
        else:
            cur.execute("DELETE FROM uom_mapping")

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


def normalizar(uom: str, diccionario: dict[str, str]) -> str:
    """Aplica el diccionario SAP→SIG (insensible a mayúsculas/espacios)."""
    return diccionario.get(uom.strip().upper(), uom.strip())
