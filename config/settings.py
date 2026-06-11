# config/settings.py

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def _project_root() -> Path:
    """Raíz del proyecto tanto en modo dev como empaquetado (PyInstaller)."""
    if getattr(sys, 'frozen', False):
        # Corriendo como .exe — el .env está junto al ejecutable
        return Path(sys.executable).parent
    # Modo desarrollo — el .env está en la raíz del proyecto
    return Path(__file__).parent.parent


PROJECT_ROOT = _project_root()
load_dotenv(PROJECT_ROOT / ".env")


SIG_DB = {
    "host":     os.getenv("SIG_HOST"),
    "user":     os.getenv("SIG_USER"),
    "password": os.getenv("SIG_PASS"),
    "database": os.getenv("SIG_DB"),
}

WEB_DB = {
    "host":     os.getenv("WEB_HOST"),
    "user":     os.getenv("WEB_USER"),
    "password": os.getenv("WEB_PASS"),
    "database": os.getenv("WEB_DB"),
}
