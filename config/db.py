# config / db.py

import os
import mysql.connector
from config.settings import SIG_DB, WEB_DB
from dotenv import load_dotenv

load_dotenv()  # Carga las variables desde el archivo .env

def get_connections():
    conn_sig = mysql.connector.connect(**SIG_DB)
    cur_sig = conn_sig.cursor(dictionary=True)

    conn_web = mysql.connector.connect(**WEB_DB)
    cur_web = conn_web.cursor(dictionary=True)

    return conn_sig, cur_sig, conn_web, cur_web

def get_store_connection(id_tienda: int):
    """
    Retorna conexión y cursor a la base de datos de la tienda específica.
    Los datos se leen de variables de entorno.
    """
    host = os.getenv(f"TIENDA_{id_tienda}_HOST")
    user = os.getenv(f"TIENDA_{id_tienda}_USER")
    password = os.getenv(f"TIENDA_{id_tienda}_PASS")
    database = os.getenv(f"TIENDA_{id_tienda}_DB")

    # print("DEBUG conexión:", host, user, database)
    conn = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        charset="utf8"
    )
    return conn, conn.cursor(dictionary=True)