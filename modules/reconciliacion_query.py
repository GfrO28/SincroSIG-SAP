import os
import json
from datetime import datetime

import pandas as pd

from config.constants import MAPEO_TIENDAS_SAP


# ── Parsing ───────────────────────────────────────────────────────────────────

def parsear_logs_para_query(logs: list) -> tuple:
    """
    Extrae los conjuntos de ítems primarios y secundarios para construir el query SAP.

    Returns:
        (primary_set, secondary_set, errores_parseo)
        Cada set contiene tuplas (ItemCode, WhsCode).
    """
    primary_set   = set()
    secondary_set = set()
    errores       = []

    for l in logs:
        try:
            js     = json.loads(l['json'])
            id_str = str(l['idtienda']).zfill(2)
            whs    = MAPEO_TIENDAS_SAP.get(id_str)
            if not whs:
                continue
            try:
                start = int(l['message'].split('line: ')[1].split(']')[0]) - 1
            except Exception:
                errores.append(_build_error_entry(l, js))
                continue
            for i, line in enumerate(js.get('DocumentLines', [])):
                key = (line['ItemCode'], whs)
                if i == start:
                    primary_set.add(key)
                else:
                    secondary_set.add(key)
        except Exception:
            continue

    return primary_set, secondary_set, errores


def parsear_logs_para_cruce(logs: list) -> tuple:
    """
    Convierte los registros de log_transfer_sunsap en filas individuales por línea de documento.

    Returns:
        (logs_procesados, errores_parseo)
        logs_procesados: lista de dicts con whs, id_sig, id_mov, fecha, item, qty, is_primary.
    """
    primary_items_global = _recolectar_primarios_globales(logs)

    procesados = []
    errores    = []

    for l in logs:
        try:
            js      = json.loads(l['json'])
            id_str  = str(l['idtienda']).zfill(2)
            whs_sap = MAPEO_TIENDAS_SAP.get(id_str)
            if not whs_sap:
                continue
            try:
                primary_idx = int(l['message'].split('line: ')[1].split(']')[0]) - 1
            except Exception:
                errores.append(_build_error_entry(l, js))
                continue
            lines = js.get('DocumentLines', [])
            for i, line in enumerate(lines):
                is_primary = (i == primary_idx)
                procesados.append({
                    'whs':        whs_sap,
                    'id_sig':     int(l['idtienda']),
                    'id_mov':     l['idmovimiento'],
                    'fecha':      l['fecha'],
                    'item':       line['ItemCode'],
                    'qty':        float(line['Quantity']),
                    'is_primary': is_primary,
                })
        except Exception:
            continue

    return procesados, errores


def _recolectar_primarios_globales(logs: list) -> set:
    """Pre-pase: recolecta todos los (ItemCode, WhsCode) que son primarios en algún registro."""
    primary_items = set()
    for l in logs:
        try:
            js   = json.loads(l['json'])
            whs  = MAPEO_TIENDAS_SAP.get(str(l['idtienda']).zfill(2))
            if not whs:
                continue
            pidx  = int(l['message'].split('line: ')[1].split(']')[0]) - 1
            lines = js.get('DocumentLines', [])
            if pidx < len(lines):
                primary_items.add((lines[pidx]['ItemCode'], whs))
        except Exception:
            pass
    return primary_items


def _build_error_entry(log_row: dict, js: dict) -> dict:
    return {
        'fecha':         log_row.get('fecha', '?'),
        'idtienda':      log_row.get('idtienda', '?'),
        'idmovimiento':  log_row.get('idmovimiento', '?'),
        'created_at':    log_row.get('created_at', '?'),
        'message':       log_row.get('message', ''),
        'document_lines': [
            f"#{j+1:>3}  ItemCode: {dl.get('ItemCode','?'):<20}  Qty: {dl.get('Quantity','?')}"
            for j, dl in enumerate(js.get('DocumentLines', []))
        ],
    }


# ── Query building ─────────────────────────────────────────────────────────────

_SAP_QUERY_HEADER = (
    'SELECT T0."ItemCode",T0."Warehouse" "WhsCode",'
    'CAST(SUM(T0."InQty"-T0."OutQty") AS DECIMAL(19,4)) "Stock_A_Fecha" '
    'FROM OINM T0 WHERE '
)
_SAP_QUERY_FOOTER = ' GROUP BY T0."ItemCode",T0."Warehouse"'
_CHAR_LIMIT       = 30_000


def construir_queries_sap(items_set: set, char_limit: int = _CHAR_LIMIT) -> list:
    """
    Construye uno o más queries SAP para la lista de (ItemCode, WhsCode).
    Divide en lotes si el query supera char_limit caracteres.
    """
    overhead    = len(_SAP_QUERY_HEADER) + len(_SAP_QUERY_FOOTER)
    conditions  = [
        f'(T0."ItemCode"=\'{item}\' AND T0."Warehouse"=\'{whs}\')'
        for item, whs in items_set
    ]

    batches, current, current_len = [], [], overhead
    for cond in conditions:
        extra = len(cond) + (4 if current else 0)
        if current and current_len + extra > char_limit:
            batches.append(current)
            current, current_len = [cond], overhead + len(cond)
        else:
            current.append(cond)
            current_len += extra
    if current:
        batches.append(current)

    return [_SAP_QUERY_HEADER + " OR ".join(b) + _SAP_QUERY_FOOTER for b in batches]


def guardar_queries(queries: list, soc_sel: str, folder: str) -> str:
    """Guarda los queries en archivos .txt y retorna la carpeta usada."""
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for i, q in enumerate(queries, 1):
        suffix = f"_parte{i}" if len(queries) > 1 else ""
        path   = os.path.join(folder, f"query_prim_sec_{soc_sel[:10].strip()}_{timestamp}{suffix}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(q)
    return folder


# ── Log de errores de parseo ───────────────────────────────────────────────────

def escribir_log_parseo(soc_sel: str, registros: list) -> tuple:
    """Escribe los registros no parseables en un archivo de texto de auditoría."""
    from config.constants import DIR_SAP_QUERY
    folder    = str(DIR_SAP_QUERY / "logs_errorparseo")
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre    = f"{soc_sel[:20].strip().replace(' ', '_')}_ERRORPARSEO_{timestamp}.txt"
    path      = os.path.join(folder, nombre)
    with open(path, "w", encoding="utf-8") as f:
        f.write("REGISTROS OMITIDOS — MESSAGE NO RECONOCIDO\n")
        f.write(f"Sociedad : {soc_sel}\n")
        f.write(f"Generado : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total    : {len(registros)} registro(s)\n")
        f.write("=" * 65 + "\n\n")
        for i, r in enumerate(registros, 1):
            f.write(f"[{i}]\n")
            f.write(f"  Fecha         : {r['fecha']}\n")
            f.write(f"  Creado        : {r.get('created_at', '?')}\n")
            f.write(f"  Tienda (ID)   : {r['idtienda']}\n")
            f.write(f"  ID Movimiento : {r['idmovimiento']}\n")
            f.write(f"  Message       : {r['message']}\n")
            dl = r.get('document_lines', [])
            f.write(f"  DocumentLines : {len(dl)} línea(s)\n")
            for d in dl:
                f.write(f"    {d}\n")
            f.write("\n")
    return nombre, path
