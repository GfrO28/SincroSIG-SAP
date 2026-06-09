# config / settings.py

import os
from dotenv import load_dotenv

load_dotenv()  # Carga las variables desde el archivo .env

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