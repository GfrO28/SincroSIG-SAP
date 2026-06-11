# config/auth.py

import os
import mysql.connector
from config.settings import SIG_DB


def _load_key() -> list:
    raw = os.getenv("SIG_CIPHER_KEY", "")
    if not raw:
        raise EnvironmentError(
            "Variable de entorno SIG_CIPHER_KEY no definida. "
            "Configúrala en el archivo .env."
        )
    return [int(x.strip()) for x in raw.split(",")]


def _encrypt_clave(plain: str) -> str:
    key = _load_key()
    result = []
    for i, c in enumerate(plain):
        b1 = ord(c) + key[(i * 2)     % len(key)]
        b2 = ord(c) + key[(i * 2 + 1) % len(key)]
        result.append(bytes([b1]).decode('cp1252'))
        result.append(bytes([b2]).decode('cp1252'))
    return ''.join(result)


_CAMPOS_USUARIO = "idusuario, nombre, apellido, cargo, desccargo, activo, clave"


def verificar_usuario_sig(idusuario: str, clave_plain: str):
    """
    Verifica credenciales contra la tabla usuarios de SIG.
    Retorna dict con los datos públicos del usuario si es correcto, None si no.
    """
    try:
        conn = mysql.connector.connect(**SIG_DB)
        cur  = conn.cursor(dictionary=True)
        try:
            cur.execute(
                f"SELECT {_CAMPOS_USUARIO} FROM usuarios WHERE idusuario = %s",
                (idusuario,)
            )
            row = cur.fetchone()
            if not row:
                return None
            stored = row.pop('clave', '') or ''   # extraer y descartar antes de retornar
            if stored == _encrypt_clave(clave_plain):
                return row
            return None
        finally:
            cur.close()
            conn.close()
    except mysql.connector.Error:
        raise ConnectionError("No se pudo conectar al servidor de autenticación.")
    except EnvironmentError:
        raise
