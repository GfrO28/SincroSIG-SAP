# modules / formulaciones_service.py

from config.db import get_store_connection, get_connections
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# ==========================================
# INSUMOS RELACIONADOS A FORMULAS
# ==========================================
def obtener_formulas_por_insumos(cur, ids_insumos):
    if not ids_insumos:
        return []

    placeholders = ",".join(["%s"] * len(ids_insumos))

    query = f"""
        SELECT DISTINCT f.idarticulos
        FROM formulacion f
        INNER JOIN formulaciondet fd 
            ON f.idformulacion = fd.idformulacion
        WHERE fd.idarticulos IN ({placeholders})
    """

    cur.execute(query, ids_insumos)
    return [r["idarticulos"] for r in cur.fetchall()]


# ==========================================
# FORMULACIÓN SIG (LISTADO GENERAL)
# ==========================================
def obtener_formulaciones_sig():
    conn_sig, cur_sig, _, _ = get_connections()
    try:
        cur_sig = conn_sig.cursor(dictionary=True)

        cur_sig.execute("""
            SELECT DISTINCT
                f.idarticulos AS idarticulo,
                f.descripcion
            FROM formulacion f
            INNER JOIN formulaciondet fd ON fd.idformulacion = f.idformulacion
            LEFT JOIN preciart p ON p.idarticulos = f.idarticulos 
            WHERE f.activo = 1
              AND p.estado = 1
              AND f.descripcion NOT LIKE '%DLVY'
            GROUP BY f.idarticulos
            ORDER BY f.descripcion
        """)

        return [(r["idarticulo"], r["descripcion"]) for r in cur_sig.fetchall()]

    finally:
        cur_sig.close()
        conn_sig.close()

# ==========================================
# DETALLE DE UNA FORMULACIÓN
# ==========================================
def obtener_detalle_formulacion(cur, idformulacion):

    query = """
        SELECT
            fd.idarticulos,
            COALESCE(a.descrip1, '') AS insumo,
            fd.cantidad,
            COALESCE(u.descrip, '') AS unidad,
            TRIM(SUBSTRING(al.descripcion, LOCATE('-', al.descripcion) + 1)) AS almacen,
            COALESCE(f.descripcion, '') AS formula_desc
        FROM formulaciondet fd
        INNER JOIN formulacion f ON f.idformulacion = fd.idformulacion
        LEFT JOIN articulos a ON a.idarticulos = fd.idarticulos
        LEFT JOIN unidadmed u ON u.idunidadmed = fd.idunidadmed
        INNER JOIN almacenes al ON al.idalmacen = fd.idalmacen
        WHERE fd.idformulacion = %s
    """

    cur.execute(query, (idformulacion,))
    rows = cur.fetchall()

    if not rows:
        return None, None

    detalles = {
        int(r["idarticulos"]): {
            "insumo": r["insumo"],
            "cantidad": r["cantidad"],
            "unidad": r["unidad"],
            "almacen": r["almacen"].strip().upper()
        }
        for r in rows
    }

    return detalles, rows[0]["formula_desc"]


# ==========================================
# ID FORM POR ARTÍCULO (TIENDA)
# ==========================================
def obtener_idformulacion_por_articulo(conn, cur, idarticulo, idtienda):
    query = """
        SELECT f.idformulacion
        FROM formulacion f
        WHERE f.idarticulos = %s
          AND f.idtienda = %s
          AND f.activo = 1
        ORDER BY f.idformulacion DESC
        LIMIT 1
    """

    cur.execute(query, (idarticulo, idtienda))
    row = cur.fetchone()

    return row["idformulacion"] if row else None


# ==========================================
# BATCH ID FORM (OPTIMIZACIÓN)
# ==========================================
def obtener_idformulacion_batch(cur, idtienda, articulos):

    if not articulos:
        return {}

    placeholders = ",".join(["%s"] * len(articulos))

    query = f"""
        SELECT f.idarticulos,
               MAX(f.idformulacion) AS idformulacion
        FROM formulacion f
        WHERE f.idtienda = %s
          AND f.activo = 1
          AND f.idarticulos IN ({placeholders})
        GROUP BY f.idarticulos
    """

    cur.execute(query, [idtienda] + articulos)

    return {
        int(r["idarticulos"]): r["idformulacion"]
        for r in cur.fetchall()
    }


# ==========================================
# BATCH DETALLES (OK, SOLO OPTIMIZACIÓN)
# ==========================================
def obtener_detalles_formulaciones_batch(cur, idforms):

    if not idforms:
        return {}

    placeholders = ",".join(["%s"] * len(idforms))

    query = f"""
        SELECT
            fd.idformulacion,
            fd.idarticulos,
            COALESCE(a.descrip1, '') AS insumo,
            fd.cantidad,
            COALESCE(u.descrip, '') AS unidad,
            TRIM(SUBSTRING(al.descripcion, LOCATE('-', al.descripcion) + 1)) AS almacen,
            COALESCE(f.descripcion, '') AS formula_desc
        FROM formulaciondet fd
        INNER JOIN formulacion f ON f.idformulacion = fd.idformulacion
        LEFT JOIN articulos a ON a.idarticulos = fd.idarticulos
        LEFT JOIN unidadmed u ON u.idunidadmed = fd.idunidadmed
        INNER JOIN almacenes al ON al.idalmacen = fd.idalmacen
        WHERE fd.idformulacion IN ({placeholders})
    """

    cur.execute(query, idforms)
    rows = cur.fetchall()

    resultado = {}

    for r in rows:
        idf = str(r["idformulacion"])

        if idf not in resultado:
            resultado[idf] = {
                "descripcion": r["formula_desc"],
                "detalles": {}
            }

        resultado[idf]["detalles"][int(r["idarticulos"])] = {
            "insumo": r["insumo"],
            "cantidad": r["cantidad"],
            "unidad": r["unidad"],
            "almacen": r["almacen"].strip().upper()
        }

    return resultado 



# modules/formulaciones_service.py

def obtener_idformulacion_batch_multi(cur, tiendas, articulos):
    """
    Retorna:
    {(idart, idtienda): idformulacion}
    """

    if not tiendas or not articulos:
        return {}

    placeholders_art = ",".join(["%s"] * len(articulos))
    placeholders_tda = ",".join(["%s"] * len(tiendas))

    query = f"""
        SELECT
            f.idarticulos,
            f.idtienda,
            MAX(f.idformulacion) AS idformulacion
        FROM formulacion f
        WHERE f.idarticulos IN ({placeholders_art})
          AND f.idtienda IN ({placeholders_tda})
          AND f.activo = 1
        GROUP BY f.idarticulos, f.idtienda
    """

    cur.execute(query, articulos + tiendas)

    return {
        (int(r["idarticulos"]), int(r["idtienda"])): r["idformulacion"]
        for r in cur.fetchall()
    }