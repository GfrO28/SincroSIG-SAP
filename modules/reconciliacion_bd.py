import pandas as pd
from config.db import get_connections
from config.constants import MAPEO_TIENDAS_SAP


def obtener_sociedades() -> list:
    """Retorna lista de dicts con idempresas, rs1, ruc para las sociedades activas."""
    conn_sig, cur_sig, _, _ = get_connections()
    cur_sig.execute("""
        SELECT e.idempresas, e.rs1, e.ruc
        FROM empresas e
        LEFT JOIN tienda t ON t.idempresas = e.idempresas AND t.activo = 1
        WHERE t.nomb_abrev <> '' AND e.idempresas NOT IN (59, 124)
        GROUP BY e.idempresas
        ORDER BY e.idempresas * 1
    """)
    return cur_sig.fetchall()


def obtener_tiendas_csv(id_empresa: int) -> str:
    """Retorna string CSV con los idtienda activos de la empresa."""
    conn_sig, cur_sig, _, _ = get_connections()
    cur_sig.execute(
        "SELECT idtienda FROM tienda WHERE idempresas = %s AND activo = 1",
        (id_empresa,)
    )
    return ",".join([str(r['idtienda']) for r in cur_sig.fetchall()])


def cargar_logs_bd(cur_sig, tiendas_csv: str, f_desde: str, f_hasta: str) -> list:
    """
    Carga registros de log_transfer_sunsap para el rango de fechas dado.
    Deduplica por idmovimiento, conservando el de mayor created_at.
    """
    cur_sig.execute(
        f"SELECT idtienda, fecha, json, message, idmovimiento, created_at "
        f"FROM log_transfer_sunsap "
        f"WHERE fecha BETWEEN %s AND %s "
        f"  AND registered = 0 "
        f"  AND nomtabla LIKE %s "
        f"  AND idtienda IN ({tiendas_csv})",
        (f_desde, f_hasta, "%salidas%")
    )
    logs_raw = cur_sig.fetchall()

    seen = {}
    for l in logs_raw:
        mid = l['idmovimiento']
        if mid not in seen or l['created_at'] > seen[mid]['created_at']:
            seen[mid] = l
    return list(seen.values())


def cargar_saldos(cur_sig, tiendas_csv: str, items_list: str) -> pd.DataFrame:
    """
    Carga los saldos SIG para los ítems y tiendas dados.
    Agrega la columna WhsCode mapeada desde MAPEO_TIENDAS_SAP.
    Retorna una fila por (ItemCode, idtienda) con el fproceso más reciente.
    """
    cur_sig.execute(
        f"SELECT fproceso, saldoinicial, ingresos, salidas, costoprom, "
        f"       idproductos AS ItemCode, idtienda "
        f"FROM saldos "
        f"WHERE idtienda IN ({tiendas_csv}) AND idproductos IN ({items_list})"
    )
    df = pd.DataFrame(cur_sig.fetchall())
    if df.empty:
        return df
    df['WhsCode'] = df['idtienda'].astype(str).str.zfill(2).map(MAPEO_TIENDAS_SAP)
    df = df.sort_values('fproceso', ascending=False).drop_duplicates(['ItemCode', 'idtienda'])
    return df
