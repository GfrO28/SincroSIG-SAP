# preciart_service

def obtener_info_articulo(cur, idarticulo):
    """
    Retorna:
    - None → no existe
    - estado (int) → existe
    """
    cur.execute(
        """
        SELECT estado
        FROM preciart
        WHERE idarticulos = %s
        LIMIT 1
        """,
        (idarticulo,)
    )
    row = cur.fetchone()
    return row["estado"] if row else None


def articulo_valido_para_formulacion(cur, idarticulo, cache=None):
    """
    Versión optimizada con cache opcional.
    """
    if cache is not None and idarticulo in cache:
        return cache[idarticulo]

    estado = obtener_info_articulo(cur, idarticulo)
    valido = estado == 1

    if cache is not None:
        cache[idarticulo] = valido

    return valido