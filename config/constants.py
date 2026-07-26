from pathlib import Path

# ── Carpetas de salida (Documentos del usuario) ────────────────────────────────
_BASE = Path.home() / "Documents" / "SincroSIGSAP"

DIR_SAP_QUERY    = _BASE / "SAP" / "QuerySAP"          # queries generados para SAP
DIR_SAP_RECON    = _BASE / "SAP" / "Reconciliaciones"   # Excel de auditoría
DIR_QUERY_SIG    = _BASE / "QuerySIG"                   # Personal / Tienda / Cargos
DIR_FORM_COMP    = _BASE / "Formulaciones" / "Comparativo SIG vs TDA"
DIR_FORM_REPORTE = _BASE / "Formulaciones" / "Reporte Formulaciones"


MAPEO_TIENDAS_SAP = {
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
    "106": "67",
}
