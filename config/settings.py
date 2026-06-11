# config / settings.py

import os
from pathlib import Path
from dotenv import load_dotenv

# Ruta absoluta al .env en la raíz del proyecto, independiente del CWD
load_dotenv(Path(__file__).parent.parent / ".env")

SIG_DB = {
    "host": os.getenv("SIG_HOST"),
    "user": os.getenv("SIG_USER"),
    "password": os.getenv("SIG_PASS"),
    "database": os.getenv("SIG_DB"),
}

WEB_DB = {
    "host": os.getenv("WEB_HOST"),
    "user": os.getenv("WEB_USER"),
    "password": os.getenv("WEB_PASS"),
    "database": os.getenv("WEB_DB"),
}