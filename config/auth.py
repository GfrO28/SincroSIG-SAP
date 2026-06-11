# config/auth.py

import mysql.connector
from config.settings import SIG_DB

_CLAVE = "%ü&/@#$A"


def _bytes_to_mysql_latin1(s: str) -> str:
    """
    El cifrador produce chars cuyo ordinal es el byte resultante (0-255).
    MySQL almacena esos bytes en una columna latin1 (internamente cp1252).
    mysql.connector los decodifica como cp1252 al enviarlos al cliente.
    Esta función replica esa conversión para que la comparación sea correcta.
    Bytes indefinidos en cp1252 (0x81, 0x8D, 0x8F, 0x90, 0x9D) se devuelven
    como el codepoint Unicode directo (igual que haría MySQL con latin1).
    """
    out = ""
    for c in s:
        b = ord(c) & 0xFF
        try:
            out += bytes([b]).decode('cp1252')
        except UnicodeDecodeError:
            out += chr(b)
    return out


def _encrypt_clave(alias: str, psw: str) -> str:
    """
    Replica de Encriptar(USU, PSW) del SIG VB.NET.
    USU = campo `alias` del usuario (ej: "52392-CCATAMAYO").

    Paso 1: XOR de cada char del PSW con _CLAVE cíclica → hex uppercase 2 dígitos por char
    Paso 2: Cada char del hex se suma con el char de alias cíclico (índice +1 en VB → (i+1)%len)
    Resultado normalizado a cp1252 para coincidir con lo que retorna mysql.connector.
    """
    usu = alias.upper()
    if not usu:
        return psw

    pass2 = ""
    for i, car in enumerate(psw):
        xor_val = ord(_CLAVE[i % len(_CLAVE)]) ^ ord(car)
        pass2 += f"{xor_val:02X}"

    raw = ""
    for i, c in enumerate(pass2):
        raw += chr((ord(c) + ord(usu[(i + 1) % len(usu)])) & 0xFF)

    return _bytes_to_mysql_latin1(raw)


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

            stored = (row.pop('clave', '') or '')
            alias  = (row.get('alias', '') or '').strip()

            if not alias:
                return None

            if stored == _encrypt_clave(alias, clave_plain):
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
