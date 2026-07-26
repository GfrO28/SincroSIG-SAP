"""
Módulo de actualizaciones automáticas vía GitHub Releases.

Flujo:
  1. verificar_actualizacion() → consulta la API y retorna info si hay versión nueva
  2. descargar_e_instalar()   → descarga el installer y lo ejecuta en silencio
"""

import os
import subprocess
import tempfile
import threading
from pathlib import Path

import requests

from version import __version__, GITHUB_REPO, APP_EXE


def _token() -> str | None:
    return os.getenv("GITHUB_TOKEN") or None


def _parsear_version(tag: str) -> tuple:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def verificar_actualizacion() -> dict | None:
    """
    Consulta la API de GitHub Releases.

    Returns:
        dict con keys {version, tag, url_descarga, notas} si hay versión nueva.
        None si ya está en la última versión o no hay releases.
    Raises:
        ConnectionError si no se puede contactar GitHub.
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    if _token():
        headers["Authorization"] = f"token {_token()}"

    try:
        resp = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers=headers,
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"No se pudo conectar a GitHub: {e}")

    if resp.status_code == 404:
        return None  # No hay releases publicados aún

    resp.raise_for_status()
    data = resp.json()

    tag_remoto = data.get("tag_name", "")
    if not tag_remoto:
        return None

    try:
        if _parsear_version(tag_remoto) <= _parsear_version(__version__):
            return None  # Ya tenemos la versión más reciente
    except ValueError:
        return None

    # Buscar el .exe instalador en los assets
    url_exe = None
    nombre_exe = None
    for asset in data.get("assets", []):
        if asset["name"].lower().endswith(".exe"):
            url_exe    = asset["browser_download_url"]
            nombre_exe = asset["name"]
            break

    return {
        "version":       tag_remoto,
        "url_descarga":  url_exe,
        "nombre_archivo": nombre_exe or f"{APP_EXE}",
        "notas":         data.get("body", "Sin notas de versión."),
        "titulo":        data.get("name", tag_remoto),
    }


def descargar_e_instalar(
    info: dict,
    progreso_fn=None,
    on_error=None,
) -> None:
    """
    Descarga el instalador en un hilo de fondo y lo ejecuta al terminar.

    Args:
        info:        dict retornado por verificar_actualizacion()
        progreso_fn: callable(porcentaje: float) para actualizar UI
        on_error:    callable(mensaje: str) si falla la descarga
    """
    def _tarea():
        try:
            url    = info["url_descarga"]
            nombre = info["nombre_archivo"]

            headers = {}
            if _token():
                headers["Authorization"] = f"token {_token()}"

            resp = requests.get(url, headers=headers, stream=True, timeout=120)
            resp.raise_for_status()

            total       = int(resp.headers.get("content-length", 0))
            descargado  = 0
            tmp_dir     = tempfile.mkdtemp(prefix="sincrosig_update_")
            ruta_local  = Path(tmp_dir) / nombre

            with open(ruta_local, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65_536):
                    f.write(chunk)
                    descargado += len(chunk)
                    if progreso_fn and total:
                        progreso_fn(descargado / total * 100)

            if progreso_fn:
                progreso_fn(100)

            # Lanzar el instalador en silencio y salir
            # /SILENT: instala sin ventanas pero muestra progreso
            # /NORESTART: no reiniciar Windows automáticamente
            subprocess.Popen(
                [str(ruta_local), "/SILENT", "/NORESTART"],
                creationflags=subprocess.DETACHED_PROCESS,
            )
            os._exit(0)

        except Exception as e:
            if on_error:
                on_error(str(e))

    threading.Thread(target=_tarea, daemon=True).start()
