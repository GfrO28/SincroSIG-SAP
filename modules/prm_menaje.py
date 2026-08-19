# modules/prm_menaje.py
"""
Lógica de negocio para Diferencias Menaje (módulo PRM).
Acepta DataFrames provenientes tanto de Excel como de query futuro.

Estructura de columnas esperada
--------------------------------
Compras : TIENDA, GRUPO, FECHA, NRO_DOC, ARTICULO, TOTAL  (+ otras)
Gastos  : IDTIENDA, GRUPOPRM, TIPO, FECHA, ORDEN, OBSERVACIONES, TOTAL  (+ otras)
          ⚠ los encabezados de gastos están en la FILA 2 del Excel (header=1)
"""

import pandas as pd
from pathlib import Path

# ─── Nombres de columnas en los Excel de origen ───────────────────────────────
_COMPRAS_COL_TDA   = "TIENDA"
_GASTOS_COL_TDA    = "IDTIENDA"
_COL_TOTAL         = "TOTAL"
_COL_FECHA         = "FECHA"

TIPOS_GASTO_MENAJE = frozenset([
    "Compra de Insumos",
    "Ing x Compra",
    "Menaje y Utensilios",
    "Publicidad",
    "Publicidad ND",
    "Venta a Tienda",
])

# Campos extraídos para el cruce detallado (columna_real → etiqueta_display)
DETALLE_COMPRAS = {
    "grupo":         "GRUPO",
    "fecha":         "FECHA",
    "nro_doc":       "NRO_DOC",
    "observaciones": "ARTICULO",     # campo descriptivo equivalente en compras
    "total":         "TOTAL",
}
DETALLE_GASTOS = {
    "grupo":         "TIPO",
    "fecha":         "FECHA",
    "nro_doc":       "ORDEN",        # número de documento en gastos
    "observaciones": "OBSERVACIONES",
    "total":         "TOTAL",
}


# ─── Funciones públicas ───────────────────────────────────────────────────────

def procesar_compras(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra registros con GRUPO == 'MENAJE'.
    Agrega columna normalizada 'TDA' copiada de TIENDA.
    """
    df = df.copy()
    mask = df["GRUPO"].astype(str).str.strip().str.upper() == "MENAJE"
    df = df[mask].copy()
    df["TDA"] = df[_COMPRAS_COL_TDA]
    return df.reset_index(drop=True)


def procesar_gastos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra GRUPOPRM in {MENAJE, UNIFORM} y TIPO en TIPOS_GASTO_MENAJE.
    Agrega columna normalizada 'TDA' copiada de IDTIENDA.
    ⚠ Llamar con df leído como header=1 (encabezados en fila 2 del Excel).
    """
    df = df.copy()
    mask_grupo = df["GRUPOPRM"].astype(str).str.strip().str.upper().isin({"MENAJE + UNIFORM"})
    mask_tipo  = df["TIPO"].astype(str).str.strip().isin(TIPOS_GASTO_MENAJE)
    df = df[mask_grupo & mask_tipo].copy()
    df["TDA"] = df[_GASTOS_COL_TDA]
    return df.reset_index(drop=True)


def calcular_resumen(df_c: pd.DataFrame, df_g: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa por TDA, suma TOTAL y calcula DIF = COMPRAS - GASTOS.
    Retorna DataFrame con columnas: TDA, COMPRAS, GASTOS, DIF.
    """
    def _agg(df, col_name):
        if df.empty:
            return pd.DataFrame(columns=["TDA", col_name])
        return (df.groupby("TDA", as_index=False)[_COL_TOTAL]
                  .sum()
                  .rename(columns={_COL_TOTAL: col_name}))

    ag_c = _agg(df_c, "COMPRAS")
    ag_g = _agg(df_g, "GASTOS")
    res = pd.merge(ag_c, ag_g, on="TDA", how="outer")
    res["COMPRAS"] = pd.to_numeric(res["COMPRAS"], errors="coerce").fillna(0)
    res["GASTOS"]  = pd.to_numeric(res["GASTOS"],  errors="coerce").fillna(0)
    res["DIF"] = (res["COMPRAS"] - res["GASTOS"]).round(2)
    return res.sort_values("TDA").reset_index(drop=True)


def cruzar_tienda(df_c: pd.DataFrame, df_g: pd.DataFrame, tda) -> list:
    """
    Cruza registros de compras y gastos para la tienda `tda`.
    Matching por FECHA (normalizada a fecha sin hora) y TOTAL (tolerancia 0.01).
    Retorna lista de dicts con: 'compra', 'gasto', 'tipo'
      tipo: 'match' | 'solo_compra' | 'solo_gasto'
    Ordenados por FECHA del registro presente.
    """
    tda_s  = _tda_str(tda)
    c_rows = df_c[df_c["TDA"].apply(_tda_str) == tda_s].to_dict("records")
    g_rows = df_g[df_g["TDA"].apply(_tda_str) == tda_s].to_dict("records")

    g_used = [False] * len(g_rows)
    result = []

    for c_rec in c_rows:
        c_fecha = _fecha_str(c_rec.get(_COL_FECHA))
        c_total = _safe_float(c_rec.get(_COL_TOTAL))
        found   = None
        for j, g_rec in enumerate(g_rows):
            if g_used[j]:
                continue
            if (_fecha_str(g_rec.get(_COL_FECHA)) == c_fecha
                    and abs(_safe_float(g_rec.get(_COL_TOTAL)) - c_total) < 0.01):
                found = j
                break
        if found is not None:
            result.append({"compra": c_rec, "gasto": g_rows[found], "tipo": "match"})
            g_used[found] = True
        else:
            result.append({"compra": c_rec, "gasto": None, "tipo": "solo_compra"})

    for j, g_rec in enumerate(g_rows):
        if not g_used[j]:
            result.append({"compra": None, "gasto": g_rec, "tipo": "solo_gasto"})

    result.sort(key=lambda r: _fecha_str((r["compra"] or r["gasto"]).get(_COL_FECHA)))
    return result


# ─── Helpers privados ─────────────────────────────────────────────────────────

def _tda_str(v) -> str:
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") else s


def _fecha_str(val) -> str:
    """Normaliza FECHA a string 'YYYY-MM-DD' para comparación consistente."""
    if val is None:
        return ""
    if hasattr(val, "date"):          # datetime / Timestamp
        return val.date().isoformat()
    s = str(val).strip()
    return s.split(" ")[0] if " " in s else s   # quita parte de hora si existe


def _safe_float(val) -> float:
    try:
        f = float(val)
        return 0.0 if f != f else f   # NaN → 0
    except (TypeError, ValueError):
        return 0.0
