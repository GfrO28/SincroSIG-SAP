# modules/diagnostico_queries.py

_CASE_TRANS = (
    'CASE T0."TransType"'
    ' WHEN 13 THEN \'Factura Venta\''
    ' WHEN 14 THEN \'NC Venta\''
    ' WHEN 15 THEN \'Entrega\''
    ' WHEN 16 THEN \'Dev. Cliente\''
    ' WHEN 18 THEN \'Factura Compra\''
    ' WHEN 20 THEN \'Recepcion OC\''
    ' WHEN 21 THEN \'Dev. Proveedor\''
    ' WHEN 59 THEN \'Ingreso Manual\''
    ' WHEN 60 THEN \'Salida Manual\''
    ' WHEN 67 THEN \'Transferencia\''
    ' ELSE TO_VARCHAR(T0."TransType") END'
)


def construir_query_config(items: list) -> str:
    """OITM: configuración UOM de todos los artículos del panel."""
    ph = ','.join(f"'{i}'" for i in sorted(set(items)))
    return (
        'SELECT T0."ItemCode",T0."ItemName",'
        'T0."InvntryUom" AS "UOM_Inventario",'
        'T0."BuyUnitMsr" AS "UOM_Compras",'
        'T0."NumInBuy" AS "Factor_Compras",'
        'T0."SalUnitMsr" AS "UOM_Ventas",'
        'T0."NumInSale" AS "Factor_Ventas",'
        'T0."OnHand" AS "Stock_SAP_Actual" '
        'FROM OITM T0 '
        f'WHERE T0."ItemCode" IN ({ph})'
    )


def construir_query_negativos(item_whs_pairs: list, fecha_desde: str) -> str:
    """OINM (vista): devoluciones y movimientos con neto negativo en el período.
    item_whs_pairs: lista de (ItemCode, WhsCode) — solo los pares con observación.
    Usa concatenación ItemCode||'-'||Warehouse porque HANA no soporta tuple-IN en vistas.
    """
    concat_vals = ','.join(f"'{i}-{w}'" for i, w in sorted(set(item_whs_pairs)))
    return (
        f'SELECT T0."ItemCode" AS "ItemCode",'
        f'T1."ItemName" AS "ItemName",'
        f'T0."DocDate" AS "Fecha",'
        f'{_CASE_TRANS} AS "Tipo",'
        'T0."BASE_REF" AS "N_Doc",'
        'T0."TransNum" AS "N_Asiento",'
        'T0."InQty" AS "Entrada",T0."OutQty" AS "Salida",'
        'T0."InQty"-T0."OutQty" AS "Neto",'
        'T0."Warehouse" AS "Almacen",'
        'COALESCE(T0."Comments",\'\') AS "Comentario",'
        'COALESCE(U1."USER_CODE",\'\') AS "Creado_Por",'
        'COALESCE(U2."USER_CODE",\'\') AS "Modifico_Asiento" '
        'FROM OINM T0 '
        'LEFT JOIN OITM T1 ON T1."ItemCode"=T0."ItemCode" '
        'LEFT JOIN OUSR U1 ON U1."USERID"=T0."UserSign" '
        'LEFT JOIN OJDT TJ ON TJ."TransId"=T0."TransNum" '
        'LEFT JOIN OUSR U2 ON U2."USERID"=TJ."UserSign2" '
        f'WHERE (T0."ItemCode"||\'-\'||T0."Warehouse") IN ({concat_vals}) '
        f'AND T0."DocDate">=\'{fecha_desde}\' '
        'AND (T0."TransType" IN (14,16,21,60) OR (T0."InQty"-T0."OutQty")<0) '
        'ORDER BY T0."ItemCode",T0."DocDate",T0."Warehouse"'
    )


def construir_query_saldos_sap(item_whs_pairs: list,
                               fecha_desde: str, fecha_hasta: str) -> str:
    """
    CTE sobre OINM: movimientos diarios del período + stock neto previo al inicio.
    item_whs_pairs: lista de (ItemCode, WhsCode) — solo los pares con observación.
    fecha_desde / fecha_hasta en formato YYYYMMDD.
    Columna Stock_Previo = InQty-OutQty acumulado ANTES de fecha_desde (saldo inicial SAP).
    Usa concatenación ItemCode||'-'||Warehouse porque HANA no soporta tuple-IN en vistas.
    """
    concat_vals = ','.join(f"'{i}-{w}'" for i, w in sorted(set(item_whs_pairs)))
    ph_i = ','.join(f"'{i}'" for i in sorted({i for i, _ in item_whs_pairs}))
    return (
        'WITH movs AS ('
        f'SELECT T0."ItemCode" AS "ItemCode",'
        f'T0."DocDate" AS "Fecha",'
        f'T0."Warehouse" AS "Almacen",'
        f'SUM(T0."InQty") AS "Ingresos_SAP",'
        f'SUM(T0."OutQty") AS "Salidas_SAP" '
        f'FROM OINM T0 '
        f'WHERE (T0."ItemCode"||\'-\'||T0."Warehouse") IN ({concat_vals}) '
        f'AND T0."DocDate">=\'{fecha_desde}\' '
        f'AND T0."DocDate"<=\'{fecha_hasta}\' '
        f'GROUP BY T0."ItemCode",T0."DocDate",T0."Warehouse"'
        '),inicial AS ('
        f'SELECT T1."ItemCode" AS "ItemCode",'
        f'T1."Warehouse" AS "Almacen",'
        f'SUM(T1."InQty"-T1."OutQty") AS "Stock_Previo" '
        f'FROM OINM T1 '
        f'WHERE (T1."ItemCode"||\'-\'||T1."Warehouse") IN ({concat_vals}) '
        f'AND T1."DocDate"<\'{fecha_desde}\' '
        f'GROUP BY T1."ItemCode",T1."Warehouse"'
        '),uom AS ('
        f'SELECT T2."ItemCode" AS "ItemCode",'
        f'T2."InvntryUom" AS "UOM_Inv" '
        f'FROM OITM T2 '
        f'WHERE T2."ItemCode" IN ({ph_i})'
        ') '
        'SELECT m."ItemCode",m."Fecha",m."Almacen",'
        'm."Ingresos_SAP",m."Salidas_SAP",'
        'COALESCE(i."Stock_Previo",0) AS "Stock_Previo",'
        'u."UOM_Inv" '
        'FROM movs m '
        'LEFT JOIN inicial i ON i."ItemCode"=m."ItemCode" AND i."Almacen"=m."Almacen" '
        'LEFT JOIN uom u ON u."ItemCode"=m."ItemCode" '
        'ORDER BY m."ItemCode",m."Almacen",m."Fecha"'
    )


def construir_query_columnas_oinm() -> str:
    """Descubrimiento: columnas de OINM relacionadas con número de documento."""
    return (
        'SELECT "ColumnName" AS "Columna","DataTypeName" AS "Tipo","Length" AS "Long" '
        'FROM SYS.TABLE_COLUMNS '
        'WHERE "TableName"=\'OINM\' AND "SchemaName"=CURRENT_SCHEMA '
        'AND (UPPER("ColumnName") LIKE \'%DOC%\' '
        'OR UPPER("ColumnName") LIKE \'%NUM%\' '
        'OR UPPER("ColumnName") LIKE \'%REF%\' '
        'OR UPPER("ColumnName") LIKE \'%TRANS%\' '
        'OR UPPER("ColumnName") LIKE \'%BASE%\') '
        'ORDER BY "ColumnName"'
    )


def construir_query_uom_sap() -> str:
    """OUOM: unidades de medida configuradas en SAP B1."""
    return (
        'SELECT T0."UomCode" AS "Código_UOM", T0."UomName" AS "Nombre_UOM" '
        'FROM OUOM T0 '
        'ORDER BY T0."UomCode"'
    )


def construir_query_historial(item: str, whs: str) -> str:
    """OINM (vista): historial completo con stock acumulado para un artículo/almacén.
    Orden por DocDate + TransNum (TransNum es único por asiento — reemplaza DocEntry).
    """
    return (
        'SELECT T0."DocDate" AS "Fecha",'
        f'{_CASE_TRANS} AS "Tipo",'
        'T0."BASE_REF" AS "N_Doc",'
        'T0."TransNum" AS "N_Asiento",'
        'T0."InQty" AS "Entrada",T0."OutQty" AS "Salida",'
        'SUM(T0."InQty"-T0."OutQty") OVER ('
        'PARTITION BY T0."ItemCode",T0."Warehouse" '
        'ORDER BY T0."DocDate",T0."TransNum" '
        'ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW'
        ') AS "Stock_Acum" '
        'FROM OINM T0 '
        f'WHERE T0."ItemCode"=\'{item}\' AND T0."Warehouse"=\'{whs}\' '
        'ORDER BY T0."DocDate",T0."TransNum"'
    )
