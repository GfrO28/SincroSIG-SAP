# modules/prm_marketing.py
"""
Lógica de filtrado para Diferencias Marketing (módulo PRM).
Comparte calcular_resumen y cruzar_tienda con prm_menaje (son genéricos).

Compras : GRUPO == 'MARKETING'
Gastos  : GRUPOPRM in {'MARKETING', 'MERCHANDISING'}
          TIPO in TIPOS_GASTO_MARKETING
"""

import pandas as pd

_COMPRAS_COL_TDA = "TIENDA"
_GASTOS_COL_TDA  = "IDTIENDA"

# Igual que Menaje excepto 'Publicidad' y 'Menaje y Utensilios'
TIPOS_GASTO_MARKETING = frozenset([
    "Compra de Insumos",
    "Ing x Compra",
    "Publicidad ND",
    "Venta a Tienda",
])


def procesar_compras(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra GRUPO == 'MARKETING' y agrega columna normalizada TDA."""
    df = df.copy()
    mask = df["GRUPO"].astype(str).str.strip().str.upper() == "MARKETING"
    df = df[mask].copy()
    df["TDA"] = df[_COMPRAS_COL_TDA]
    return df.reset_index(drop=True)


def procesar_gastos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra GRUPOPRM in {'MARKETING', 'MERCHANDISING'} y TIPO en lista definida.
    Agrega columna normalizada TDA.
    ⚠ Llamar con df leído como header=1 (encabezados en fila 2 del Excel).
    """
    df = df.copy()
    mask_grupo = df["GRUPOPRM"].astype(str).str.strip().str.upper().isin(
        {"MARKETING", "MERCHANDISING"}
    )
    mask_tipo = df["TIPO"].astype(str).str.strip().isin(TIPOS_GASTO_MARKETING)
    df = df[mask_grupo & mask_tipo].copy()
    df["TDA"] = df[_GASTOS_COL_TDA]
    return df.reset_index(drop=True)
