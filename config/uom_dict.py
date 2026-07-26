# config/uom_dict.py
"""
Diccionario persistente SAP UOM → SIG UOM.
Se guarda en config/uom_mapping.json junto al ejecutable o en la raíz del proyecto.
"""
import json
from pathlib import Path

_DICT_PATH = Path(__file__).parent / 'uom_mapping.json'

# Valores por defecto — ampliar según necesidad
_DEFAULTS: dict[str, str] = {
    "KILOGRAMO":  "KG",
    "KILOGRAMOS": "KG",
    "GRAMO":      "GR",
    "GRAMOS":     "GR",
    "LIBRA":      "LB",
    "LIBRAS":     "LB",
    "UNIDAD":     "UND",
    "UNIDADES":   "UND",
    "PIEZA":      "PZA",
    "PIEZAS":     "PZA",
    "CAJA":       "CJA",
    "CAJAS":      "CJA",
    "PAQUETE":    "PQ",
    "PAQUETES":   "PQ",
    "BULTO":      "BTO",
    "BULTOS":     "BTO",
    "LITRO":      "LT",
    "LITROS":     "LT",
    "METRO":      "MT",
    "METROS":     "MT",
    "DOCENA":     "DOC",
    "DOCENAS":    "DOC",
}


def cargar() -> dict[str, str]:
    if _DICT_PATH.exists():
        try:
            with open(_DICT_PATH, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return dict(_DEFAULTS)


def guardar(d: dict[str, str]) -> None:
    with open(_DICT_PATH, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2, sort_keys=True)


def normalizar(uom: str, diccionario: dict[str, str]) -> str:
    """Aplica el diccionario SAP→SIG (insensible a mayúsculas/espacios)."""
    return diccionario.get(uom.strip().upper(), uom.strip())
