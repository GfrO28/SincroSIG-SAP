# config/auth.py

import mysql.connector
from config.settings import SIG_DB

# Clave derivada por análisis de "2805" → "amxd^‚}‚"
# Cada caracter de entrada produce 2 de salida usando esta clave cíclica.
_KEY = [47, 59, 64, 44, 46, 82, 72, 77]


def _encrypt_clave(plain: str) -> str:
    # Los bytes resultantes se decodifican como cp1252 (Windows-1252),
    # que es el charset que usa SIG al guardar en MySQL.
    result = []
    for i, c in enumerate(plain):
        b1 = ord(c) + _KEY[(i * 2)     % len(_KEY)]
        b2 = ord(c) + _KEY[(i * 2 + 1) % len(_KEY)]
        result.append(bytes([b1]).decode('cp1252'))
        result.append(bytes([b2]).decode('cp1252'))
    return ''.join(result)


def verificar_usuario_sig(idusuario: str, clave_plain: str):
    """
    Verifica credenciales contra la tabla usuarios de SIG.
    Retorna dict con los datos del usuario si es correcto, None si no.
    """
    try:
        # Sin forzar charset: el conector usa utf-8 por defecto,
        # que devuelve los caracteres Unicode exactos guardados por SIG.
        conn = mysql.connector.connect(**SIG_DB)
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT * FROM usuarios WHERE idusuario = %s",
                (idusuario,)
            )
            row = cur.fetchone()
            if not row:
                return None
            stored = row.get('clave', '') or ''
            if stored == _encrypt_clave(clave_plain):
                return row
            return None
        finally:
            cur.close()
            conn.close()
    except Exception:
        raise
