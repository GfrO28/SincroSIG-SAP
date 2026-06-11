# config/auth.py

import os
import mysql.connector
from config.settings import SIG_DB   # settings.py ya ejecutó load_dotenv


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


def verificar_usuario_sig(idusuario: str, clave_plain: str):
    """
    Verifica credenciales contra la tabla usuarios de SIG.
    Retorna dict con los datos del usuario (sin la clave) si es correcto, None si no.
    """
    faltantes = [k for k, v in SIG_DB.items() if not v]
    if faltantes:
        raise EnvironmentError(
            f"Faltan variables de entorno en el archivo .env: "
            f"{', '.join(f'SIG_{k.upper()}' for k in faltantes)}"
        )

    try:
        conn = mysql.connector.connect(**SIG_DB)
        cur  = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT * FROM usuarios WHERE idusuario = %s",
                (idusuario,)
            )
            row = cur.fetchone()
            if not row:
                return None
            stored = row.pop('clave', '') or ''   # descartar clave antes de retornar
            if stored == _encrypt_clave(clave_plain):
                return row
            return None
        finally:
            cur.close()
            conn.close()
    except mysql.connector.Error as e:
        raise ConnectionError(
            f"No se pudo conectar al servidor de autenticación.\n"
            f"Verificá que el equipo tenga acceso a la red del servidor.\n"
            f"Detalle: {e}"
        )
    except EnvironmentError:
        raise
