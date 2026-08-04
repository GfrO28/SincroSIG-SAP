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


def obtener_tiendas_ids(id_empresa: int) -> list:
    """Retorna lista de idtienda activos de la empresa."""
    conn_sig, cur_sig, _, _ = get_connections()
    cur_sig.execute(
        "SELECT idtienda FROM tienda WHERE idempresas = %s AND activo = 1",
        (id_empresa,)
    )
    return [r['idtienda'] for r in cur_sig.fetchall()]


def cargar_logs_bd(cur_sig, tiendas_ids: list, f_desde: str, f_hasta: str) -> list:
    """
    Carga registros de log_transfer_sunsap para el rango de fechas dado.
    Deduplica por idmovimiento, conservando el de mayor created_at.
    """
    if not tiendas_ids:
        return []
    placeholders = ",".join(["%s"] * len(tiendas_ids))
    cur_sig.execute(
        f"SELECT idtienda, fecha, json, message, idmovimiento, created_at "
        f"FROM log_transfer_sunsap "
        f"WHERE fecha BETWEEN %s AND %s "
        f"  AND registered = 0 "
        f"  AND nomtabla LIKE %s "
        f"  AND idtienda IN ({placeholders})",
        (f_desde, f_hasta, "%salidas%", *tiendas_ids)
    )
    logs_raw = cur_sig.fetchall()

    seen = {}
    for l in logs_raw:
        mid = l['idmovimiento']
        if mid not in seen or l['created_at'] > seen[mid]['created_at']:
            seen[mid] = l
    return list(seen.values())


_SALDOS_COLS = ['fproceso', 'saldoinicial', 'ingresos', 'salidas',
                'costoprom', 'ItemCode', 'idtienda', 'WhsCode']


def cargar_saldos(cur_sig, tiendas_ids: list, items: list, fecha_hasta: str = None) -> pd.DataFrame:
    """
    Carga los saldos SIG para los ítems y tiendas dados.
    Agrega la columna WhsCode mapeada desde MAPEO_TIENDAS_SAP.
    Retorna una fila por (ItemCode, idtienda) con el fproceso más reciente.
    Si fecha_hasta se indica, toma el saldo vigente a esa fecha (fproceso <= fecha_hasta).
    Siempre retorna un DataFrame con las columnas correctas (nunca sin columnas).
    """
    _empty = pd.DataFrame(columns=_SALDOS_COLS)

    if not tiendas_ids or not items:
        return _empty

    ph_tiendas = ",".join(["%s"] * len(tiendas_ids))
    ph_items   = ",".join(["%s"] * len(items))

    if fecha_hasta:
        cur_sig.execute(
            f"SELECT fproceso, saldoinicial, ingresos, salidas, costoprom, "
            f"       idproductos AS ItemCode, idtienda "
            f"FROM saldos "
            f"WHERE idtienda IN ({ph_tiendas}) AND idproductos IN ({ph_items})"
            f"  AND fproceso <= %s",
            (*tiendas_ids, *items, fecha_hasta)
        )
    else:
        cur_sig.execute(
            f"SELECT fproceso, saldoinicial, ingresos, salidas, costoprom, "
            f"       idproductos AS ItemCode, idtienda "
            f"FROM saldos "
            f"WHERE idtienda IN ({ph_tiendas}) AND idproductos IN ({ph_items})",
            (*tiendas_ids, *items)
        )

    df = pd.DataFrame(cur_sig.fetchall())
    if df.empty:
        return _empty
    df['WhsCode'] = df['idtienda'].astype(str).str.zfill(2).map(MAPEO_TIENDAS_SAP)

    # Para cada (ItemCode, idtienda) quedarse solo con el fproceso más reciente,
    # luego SUMAR saldoinicial/ingresos/salidas de todos los registros de ese período
    # (artículos con doble stock en la misma fecha tienen dos filas que deben consolidarse)
    df = df.sort_values('fproceso', ascending=False)
    fproceso_reciente = df.groupby(['ItemCode', 'idtienda'])['fproceso'].transform('first')
    df = df[df['fproceso'] == fproceso_reciente]
    df = (df.groupby(['ItemCode', 'idtienda'], as_index=False)
            .agg(
                fproceso    =('fproceso',      'first'),
                WhsCode     =('WhsCode',       'first'),
                saldoinicial=('saldoinicial',   'sum'),
                ingresos    =('ingresos',       'sum'),
                salidas     =('salidas',        'sum'),
                costoprom   =('costoprom',      'first'),
            ))
    return df
