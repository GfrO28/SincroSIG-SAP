"""
Diagnóstico de autenticación SIG.
Ejecutar: python test_auth.py
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import mysql.connector
from config.settings import SIG_DB

_CLAVE = "%ü&/@#$A"


def _bytes_to_mysql_latin1(s: str) -> str:
    out = ""
    for c in s:
        b = ord(c) & 0xFF
        try:
            out += bytes([b]).decode('cp1252')
        except UnicodeDecodeError:
            out += chr(b)
    return out


def encrypt(usu: str, psw: str) -> str:
    usu = usu.upper()
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


def comparar(label: str, resultado: str, stored: str):
    match = resultado == stored
    print(f"\n  [{label}]")
    print(f"  Calculado : {resultado!r}")
    print(f"  BD        : {stored!r}")
    print(f"  Coincide  : {'✓ SÍ' if match else '✗ NO'}")
    if not match:
        print(f"  Dif bytes : ", end="")
        for i in range(max(len(resultado), len(stored))):
            rc = ord(resultado[i]) if i < len(resultado) else "—"
            sc = ord(stored[i])    if i < len(stored)    else "—"
            if rc != sc:
                print(f"pos{i}({sc}≠{rc})", end=" ")
        print()
    return match


def main():
    print("=" * 60)
    print("  Diagnóstico de autenticación SIG")
    print("=" * 60)

    idusuario = input("\nID de usuario  : ").strip()
    clave      = input("Contraseña     : ").strip()

    print("\n[1] Conectando a BD SIG...")
    try:
        conn = mysql.connector.connect(**SIG_DB)
        cur  = conn.cursor(dictionary=True)
        print("    OK")
    except Exception as e:
        print(f"    ERROR: {e}"); sys.exit(1)

    cur.execute("SELECT * FROM usuarios WHERE idusuario = %s", (idusuario,))
    row = cur.fetchone()
    if not row:
        print("    Usuario no encontrado."); cur.close(); conn.close(); return

    stored   = (row.get('clave', '') or '')
    aliasusu = (row.get('aliasusu', '') or '').strip()
    alias    = (row.get('alias',    '') or '').strip()

    print(f"\n[2] Datos del usuario:")
    print(f"    idusuario : {row.get('idusuario', '')}")
    print(f"    aliasusu  : {aliasusu!r}")
    print(f"    alias     : {alias!r}")
    print(f"    clave BD  : {stored!r}")
    print(f"    bytes BD  : {[ord(c) for c in stored]}")

    print(f"\n[3] Probando Encriptar con distintos USU:")

    vistos = set()

    def _probar(label, usu):
        if usu.upper() in vistos:
            return
        vistos.add(usu.upper())
        comparar(label, encrypt(usu, clave), stored)

    _probar(f"USU=idusuario '{idusuario}'", idusuario)
    if aliasusu:
        _probar(f"USU=aliasusu '{aliasusu}'", aliasusu)
    if alias:
        _probar(f"USU=alias '{alias}'", alias)
    if "-" in alias:
        _probar(f"USU=alias_sin_guion '{alias.split('-')[0]}'", alias.split("-")[0])

    print(f"\n[4] Campos completos del usuario:")
    for k, v in row.items():
        if k != 'clave':
            print(f"    {k:20} = {v!r}")

    cur.close(); conn.close()
    print()


if __name__ == "__main__":
    main()
