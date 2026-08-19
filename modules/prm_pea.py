# modules/prm_pea.py
"""
Lógica de datos para Diferencias PEA (módulo PRM).

Archivos fuente
---------------
COMPRAS  : TIENDA, GRUPO, CD_PROV, NRO_DOC, ARTICULO, TOTAL  (+ otras)
I&S      : T, T.MOVIMIENTO, GRUPOVAN, NRO DOC, ARTICULO, TOTAL (+ otras)
DATA PEA : T, FECHA, TIPO, TOTAL, ALMACEN
"""

import pandas as pd

GRUPOS_PEA = frozenset([
    "BUFFET", "CARNES", "CERVEZA", "ENSALADA", "GASEOSA",
    "HELADO", "INSUMOS", "LICORES", "NF", "PAPA", "POLLOS",
])

_TIPO_PEA_GV   = "PEA-GV"
_TIPO_COBRO_VAN = "COBRO VAN"


# ─── Tiendas disponibles ──────────────────────────────────────────────────────

def obtener_tiendas_pea(df_pea: pd.DataFrame) -> list:
    """Lista de tiendas únicas ordenadas numéricamente (de menor a mayor)."""
    tiendas = {_tda_str(v) for v in df_pea["T"].dropna().unique()}
    return sorted(tiendas, key=lambda x: (0, int(x)) if x.isdigit() else (1, x))


def obtener_dif_total_pea(df_pea: pd.DataFrame, tienda) -> float:
    """Suma directa PEA-GV − COBRO VAN para una tienda (sin construir el pivot completo)."""
    tda = _tda_str(tienda)
    df  = df_pea[df_pea["T"].apply(_tda_str) == tda]
    if df.empty:
        return 0.0
    tipos = df["TIPO"].astype(str).str.strip()
    pea_gv    = df[tipos == _TIPO_PEA_GV   ]["TOTAL"].sum()
    cobro_van = df[tipos == _TIPO_COBRO_VAN]["TOTAL"].sum()
    return round(float(pea_gv) - float(cobro_van), 2)


# ─── Tabla 1: pivot DATA PEA ──────────────────────────────────────────────────

def procesar_pivot_pea(df_pea: pd.DataFrame, tienda) -> pd.DataFrame:
    """
    Filtra DATA PEA por T == tienda.
    Pivot: filas=FECHA, columnas=TIPO, valores=suma(TOTAL).
    Agrega columna DIF = PEA-GV - COBRO VAN.
    Agrega fila TOTAL al final.
    """
    tda = _tda_str(tienda)
    df  = df_pea[df_pea["T"].apply(_tda_str) == tda].copy()
    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot_table(
        index="FECHA", columns="TIPO", values="TOTAL",
        aggfunc="sum", fill_value=0,
    ).reset_index()
    pivot.columns.name = None

    # Columna computada DIF
    pea_gv    = pd.to_numeric(pivot.get(_TIPO_PEA_GV,    0), errors="coerce").fillna(0)
    cobro_van = pd.to_numeric(pivot.get(_TIPO_COBRO_VAN, 0), errors="coerce").fillna(0)
    pivot["DIF"] = (pea_gv - cobro_van).round(2)

    # Fila TOTAL
    num_cols = [c for c in pivot.columns if c != "FECHA"]
    totals   = pivot[num_cols].sum().to_dict()
    totals["FECHA"] = "TOTAL"
    pivot = pd.concat([pivot, pd.DataFrame([totals])], ignore_index=True)

    return pivot


# ─── Tabla 2: facturas COMPRAS vs I&S ────────────────────────────────────────

def obtener_facturas_compras(df_c: pd.DataFrame, tienda) -> pd.DataFrame:
    """
    Filtra COMPRAS: TIENDA==tienda, CD_PROV==0, GRUPO in GRUPOS_PEA.
    Agrupa por NRO_DOC → suma TOTAL.
    Retorna columnas: NRO_DOC_CAS | TOTAL
    """
    tda = _tda_str(tienda)
    df  = df_c[df_c["TIENDA"].apply(_tda_str) == tda].copy()
    df  = df[pd.to_numeric(df["CD_PROV"], errors="coerce").fillna(-1) == 0]
    df  = df[df["GRUPO"].astype(str).str.strip().str.upper().isin(GRUPOS_PEA)]
    if df.empty:
        return pd.DataFrame(columns=["NRO_DOC_CAS", "TOTAL"])
    result = (df.groupby("NRO_DOC", as_index=False)["TOTAL"]
               .sum()
               .rename(columns={"NRO_DOC": "NRO_DOC_CAS"}))
    result["NRO_DOC_CAS"] = result["NRO_DOC_CAS"].apply(_norm_nro_doc)
    return result.sort_values("NRO_DOC_CAS").reset_index(drop=True)


def obtener_facturas_is(df_is: pd.DataFrame, tienda) -> pd.DataFrame:
    """
    Filtra I&S: T==tienda, T.MOVIMIENTO=='Ing x Pedidos de Almacen',
    GRUPOVAN in GRUPOS_PEA.
    Agrupa por 'NRO DOC' → suma TOTAL.
    Retorna columnas: NRO_DOC_CAS | TOTAL
    """
    tda = _tda_str(tienda)
    df  = df_is[df_is["T"].apply(_tda_str) == tda].copy()
    df  = df[df["T.MOVIMIENTO"].astype(str).str.strip() == "Ing x Pedidos de Almacen"]
    df  = df[df["GRUPOVAN"].astype(str).str.strip().str.upper().isin(GRUPOS_PEA)]
    if df.empty:
        return pd.DataFrame(columns=["NRO_DOC_CAS", "TOTAL"])
    result = (df.groupby("NRO DOC", as_index=False)["TOTAL"]
               .sum()
               .rename(columns={"NRO DOC": "NRO_DOC_CAS"}))
    result["NRO_DOC_CAS"] = result["NRO_DOC_CAS"].apply(_norm_nro_doc)
    return result.sort_values("NRO_DOC_CAS").reset_index(drop=True)


# ─── Cruce genérico por clave ─────────────────────────────────────────────────

def cruzar_por_clave(df_a: pd.DataFrame, df_b: pd.DataFrame,
                     col_key: str = "NRO_DOC_CAS",
                     col_val: str = "TOTAL") -> list:
    """
    Cruza df_a y df_b por col_key (facturas o artículos).
    Retorna lista de dicts: {key_a, val_a, key_b, val_b, dif, tipo}
      tipo: 'match' | 'dif' | 'solo_a' | 'solo_b'
    """
    a_d = {str(r[col_key]).strip(): _sf(r[col_val]) for _, r in df_a.iterrows()}
    b_d = {str(r[col_key]).strip(): _sf(r[col_val]) for _, r in df_b.iterrows()}

    result = []
    for key in sorted(set(a_d) | set(b_d)):
        a_val = a_d.get(key)
        b_val = b_d.get(key)
        if a_val is not None and b_val is not None:
            dif  = round(a_val - b_val, 2)
            tipo = "match" if dif == 0 else "dif"
        elif a_val is not None:
            dif, tipo = None, "solo_a"
        else:
            dif, tipo = None, "solo_b"
        result.append({
            "key_a": key if a_val is not None else "",
            "val_a": a_val,
            "key_b": key if b_val is not None else "",
            "val_b": b_val,
            "dif":   dif,
            "tipo":  tipo,
        })
    return result


# ─── Detalle por factura (artículos) ─────────────────────────────────────────

def obtener_articulos_compras(df_c: pd.DataFrame, tienda, nro_doc) -> pd.DataFrame:
    """Artículos de COMPRAS para una tienda + NRO_DOC específico. Incluye CODIGO."""
    tda = _tda_str(tienda)
    df  = df_c[df_c["TIENDA"].apply(_tda_str) == tda].copy()
    df  = df[pd.to_numeric(df["CD_PROV"], errors="coerce").fillna(-1) == 0]
    df  = df[df["GRUPO"].astype(str).str.strip().str.upper().isin(GRUPOS_PEA)]
    df  = df[df["NRO_DOC"].apply(_norm_nro_doc) == _norm_nro_doc(nro_doc)]
    if df.empty:
        return pd.DataFrame(columns=["CODIGO", "ARTICULO", "TOTAL"])
    return (df.groupby("ARTICULO", as_index=False)
              .agg(TOTAL=("TOTAL", "sum"), CODIGO=("CODIGO", "first"))
              [["CODIGO", "ARTICULO", "TOTAL"]]
              .sort_values("ARTICULO")
              .reset_index(drop=True))


def obtener_articulos_is(df_is: pd.DataFrame, tienda, nro_doc) -> pd.DataFrame:
    """Artículos de I&S para una tienda + NRO DOC específico. Incluye CODIGO."""
    tda = _tda_str(tienda)
    df  = df_is[df_is["T"].apply(_tda_str) == tda].copy()
    df  = df[df["T.MOVIMIENTO"].astype(str).str.strip() == "Ing x Pedidos de Almacen"]
    df  = df[df["GRUPOVAN"].astype(str).str.strip().str.upper().isin(GRUPOS_PEA)]
    df  = df[df["NRO DOC"].apply(_norm_nro_doc) == _norm_nro_doc(nro_doc)]
    if df.empty:
        return pd.DataFrame(columns=["CODIGO", "ARTICULO", "TOTAL"])
    return (df.groupby("ARTICULO", as_index=False)
              .agg(TOTAL=("TOTAL", "sum"), CODIGO=("CODIGO", "first"))
              [["CODIGO", "ARTICULO", "TOTAL"]]
              .sort_values("ARTICULO")
              .reset_index(drop=True))


def cruzar_articulos_pea(df_a: pd.DataFrame, df_b: pd.DataFrame) -> list:
    """
    Cruce por CODIGO (más fiable que por nombre de ARTICULO).
    df_a / df_b: DataFrames con columnas CODIGO, ARTICULO, TOTAL.
    Retorna lista de dicts: {c_cod, c_art, val_a, is_cod, is_art, val_b, dif, tipo}
    """
    a_d = {str(r["CODIGO"]).strip(): r for _, r in df_a.iterrows()}
    b_d = {str(r["CODIGO"]).strip(): r for _, r in df_b.iterrows()}

    result = []
    for key in sorted(set(a_d) | set(b_d)):
        a_rec = a_d.get(key)
        b_rec = b_d.get(key)
        a_val = _sf(a_rec["TOTAL"]) if a_rec is not None else None
        b_val = _sf(b_rec["TOTAL"]) if b_rec is not None else None
        a_art = str(a_rec["ARTICULO"]).strip() if a_rec is not None else ""
        b_art = str(b_rec["ARTICULO"]).strip() if b_rec is not None else ""
        if a_val is not None and b_val is not None:
            dif  = round(a_val - b_val, 2)
            tipo = "match" if dif == 0 else "dif"
        elif a_val is not None:
            dif, tipo = None, "solo_a"
        else:
            dif, tipo = None, "solo_b"
        result.append({
            "c_cod":  key if a_val is not None else "",
            "c_art":  a_art,
            "val_a":  a_val,
            "is_cod": key if b_val is not None else "",
            "is_art": b_art,
            "val_b":  b_val,
            "dif":    dif,
            "tipo":   tipo,
        })
    return result


# ─── Helpers privados ─────────────────────────────────────────────────────────

def _tda_str(v) -> str:
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") else s


def _norm_nro_doc(v) -> str:
    """
    Normaliza NRO_DOC eliminando ceros líderes del segmento numérico tras el guión.
    FFF1-00123456  →  FFF1-123456
    FFF1-123456    →  FFF1-123456  (ya normalizado)
    """
    s = str(v).strip()
    if "-" in s:
        prefix, num = s.split("-", 1)
        try:
            return f"{prefix}-{int(num)}"
        except (ValueError, TypeError):
            return s
    return s


def _sf(val) -> float:
    try:
        f = float(val)
        return 0.0 if f != f else f
    except (TypeError, ValueError):
        return 0.0
