from pathlib import Path

# ── Carpetas de salida (Documentos del usuario) ────────────────────────────────
_BASE = Path.home() / "Documents" / "SincroSIGSAP"

DIR_SAP_QUERY    = _BASE / "SAP" / "QuerySAP"          # queries generados para SAP
DIR_SAP_RECON    = _BASE / "SAP" / "Reconciliaciones"   # Excel de auditoría
DIR_QUERY_SIG    = _BASE / "QuerySIG"                   # Personal / Tienda / Cargos
DIR_FORM_COMP    = _BASE / "Formulaciones" / "Comparativo SIG vs TDA"
DIR_FORM_REPORTE = _BASE / "Formulaciones" / "Reporte Formulaciones"
DIR_PRM          = _BASE / "PRM"

# El mapeo idtienda → WhsCode SAP se administra desde config/tiendas_sap_dict.py
# (persistido en BD, con editor visual) — ya no vive hardcodeado aquí.
