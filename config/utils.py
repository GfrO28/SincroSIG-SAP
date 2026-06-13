# core/utils.py
import json
import os
from datetime import datetime, timedelta
from typing import Any, List, Dict, Union
from pathlib import Path
import pandas as pd
from config.db import get_connections

CACHE_DIR = "cache_datos"
CACHE_EXPIRACION_HORAS = 72

class SQLCollector:
    """
    Acumula sentencias INSERT y UPDATE en memoria y permite exportarlas
    o ejecutarlas en la base de datos.
    """
    def __init__(self):
        self._inserts: List[str] = []
        self._updates: List[str] = []
        self._lines:  List[str] = []

    # --- Agregar sentencias ---
    def add_insert(self, sql: str):
        if sql:
            self._inserts.append(sql)

    def add_update(self, sql: str):
        if sql:
            self._updates.append(sql)

    def add_line(self, text: str):
        if text:
            self._lines.append(text)

    # --- Consultar y limpiar ---
    def get_inserts(self) -> List[str]:
        return list(self._inserts)

    def get_updates(self) -> List[str]:
        return list(self._updates)
    
    def get_lines(self) -> List[str]:
        return list(self._lines)

    def total(self) -> int:
        return len(self._inserts) + len(self._updates)

    def clear(self):
        """Vacía todas las colecciones."""
        self._inserts.clear()
        self._updates.clear()
        self._lines.clear()

    # --- Exportar a archivo ---
    def export_to_file(self, nombre_base: str, carpeta: str | None = None) -> str:
        """
        Exporta todo el contenido (INSERTS + UPDATES) a un archivo TXT con fecha y hora.
        Retorna la ruta del archivo creado o cadena vacía si no hay sentencias.
        """
        instrucciones = self.get_inserts() + self.get_updates() + self.get_lines()
        if not instrucciones:
            return ""
        if carpeta is None:
            from config.constants import DIR_QUERY_SIG
            carpeta = str(DIR_QUERY_SIG)
        os.makedirs(carpeta, exist_ok=True)
        fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nombre = f"{nombre_base}_{fecha_hora}.txt"
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            for sql in instrucciones:
                f.write(sql + "\n")
        return ruta


# --- Instancia global para todo el proyecto ---
collector = SQLCollector()


# --- Funciones de compatibilidad (uso directo) ---
def agregar_insert(sql: str):
    collector.add_insert(sql)

def agregar_update(sql: str):
    collector.add_update(sql)


# --- Ejecución de SQL en base de datos ---
import time
from mysql.connector import errors

def ejecutar_sql(
    cur,
    conn,
    lista,
    nombre_tabla="tabla",
    commit_interval=50,
    progress_callback=None  # 🔥 NUEVO
):
    """
    Ejecuta una lista de sentencias SQL en la conexión indicada.
    Hace commits parciales y permite reportar progreso.
    """
    ejecutadas = 0
    total = len(lista)

    for i, sql in enumerate(lista, start=1):
        try:
            cur.execute(sql)
            ejecutadas += 1

        except Exception as e:
            msg = str(e)

            # ⚠️ Manejo de desconexión
            if "Lost connection" in msg or "MySQL server has gone away" in msg:
                print(f"⚠️ Conexión perdida al ejecutar {nombre_tabla}. Reintentando...")
                try:
                    conn.reconnect(attempts=3, delay=2)
                    cur = conn.cursor()
                    cur.execute(sql)
                    ejecutadas += 1
                except Exception as e2:
                    print(f"❌ Error tras reconexión: {e2}\nSQL: {sql}")
            else:
                print(f"❌ Error en {nombre_tabla}: {e}\nSQL: {sql}")

        # ==========================================
        # 🔥 PROGRESO REAL
        # ==========================================
        if progress_callback and total > 0:
            porcentaje = (i / total) * 100
            try:
                progress_callback(
                    porcentaje,
                    f"Ejecutando {i}/{total}"
                )
            except Exception:
                pass  # evitar romper ejecución si falla UI

        # 🧱 Commit parcial
        if i % commit_interval == 0:
            try:
                if not conn.is_connected():
                    conn.reconnect(attempts=3, delay=2)
                conn.ping(reconnect=True, attempts=3, delay=2)
                conn.commit()
                print(f"💾 Commit parcial realizado ({i} sentencias).")
            except Exception as e:
                print(f"⚠️ Commit parcial falló ({i}): {e}")
                try:
                    conn.reconnect(attempts=3, delay=2)
                    cur = conn.cursor()
                except Exception as e2:
                    print(f"❌ No se pudo reconectar tras fallo de commit: {e2}")

    # ==========================================
    # ✅ Commit final
    # ==========================================
    try:
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=2)
        conn.ping(reconnect=True, attempts=3, delay=2)
        conn.commit()
    except Exception as e:
        print(f"⚠️ Commit final falló: {e}")
    else:
        print(f"✅ {ejecutadas} instrucciones ejecutadas en {nombre_tabla}.")

def obtener_tiendas_sig():
    """
    Devuelve una lista de tuplas (idtienda, nombre_mostrado, tipo)
    tipo = 1 (Lima), 2 (Provincia), 3 (Hotel)
    """
    conn_sig, cur_sig, _, _ = get_connections()
    try:
        cur_sig = conn_sig.cursor(dictionary=True)
        cur_sig.execute("""
            SELECT
                idtienda AS id,
                CONCAT(idtienda, ' - ', nombre) AS nombre,
                CASE
                    WHEN tienda.provincia = 1 AND tienda.hotel_clasificacion = 0 THEN 2
                    WHEN tienda.hotel_clasificacion = 1 THEN 3
                    ELSE 1
                END AS tipo
            FROM tienda 
            WHERE principal = 0 
              AND activo = 1 
              AND dsn IS NOT NULL 
              AND dsn <> '--' 
              AND idtienda NOT IN (4, 70, 10, 39, 47, 87, 78, 66, 79, 81, 77, 89, 90, 3011) 
            ORDER BY CAST(idtienda AS SIGNED);
        """)
        return [(row["id"], row["nombre"], row["tipo"]) for row in cur_sig.fetchall()]
    finally:
        cur_sig.close()
        conn_sig.close()

def _ruta_cache(nombre):
    """Devuelve la ruta completa al archivo de cache."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    return os.path.join(CACHE_DIR, f"{nombre}.json")

def guardar_cache(nombre, data):
    """Guarda cualquier tipo de dato en cache (en formato JSON)."""
    ruta = _ruta_cache(nombre)
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Advertencia] No se pudo guardar cache {nombre}: {e}")

def cargar_cache(nombre):
    """
    Carga el cache si existe y no ha expirado.
    Retorna None si no existe o está vencido.
    """
    ruta = _ruta_cache(nombre)
    if not os.path.exists(ruta):
        return None

    # Verificar expiración
    mtime = datetime.fromtimestamp(os.path.getmtime(ruta))
    if datetime.now() - mtime > timedelta(hours=CACHE_EXPIRACION_HORAS):
        print(f"[Cache] Expirado: {nombre}")
        return None

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Error] No se pudo leer cache {nombre}: {e}")
        return None

def export_excel(
    data: Union["pd.DataFrame", List[Dict[str, Any]], None],
    nombre_base: str,
    sheet_name: str = "Sheet1",
    carpeta: str | None = None,
) -> str:
    """
    Exporta `data` a un archivo Excel (.xlsx) y devuelve la ruta del archivo generado.
    - `data` puede ser:
        * un pandas.DataFrame (si pandas está instalado), o
        * una lista de diccionarios [{col: val, ...}, ...]
    - `nombre_base` es el prefijo del archivo (se añade timestamp).
    - `sheet_name` nombre de la hoja.
    - `carpeta` carpeta donde guardar (se crea si no existe).
    Retorna la ruta del archivo o cadena vacía si no se pudo generar.
    """
    if data is None:
        return ""

    # Crear carpeta destino
    if carpeta is None:
        from config.constants import DIR_FORM_REPORTE
        carpeta = str(DIR_FORM_REPORTE)
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre = f"{nombre_base}_{fecha_hora}.xlsx"
    ruta = Path(carpeta) / nombre

    # Intentar con pandas (si está disponible)
    try:
        import pandas as pd  # type: ignore
        if isinstance(data, pd.DataFrame):
            df = data
        else:
            # asumir lista de dicts o similar
            df = pd.DataFrame(data)
        # si df está vacío, no crear archivo
        if df.empty:
            return ""
        df.to_excel(ruta, sheet_name=sheet_name, index=False)
        return str(ruta)
    except Exception:
        # fallback a openpyxl (si pandas no está o falla)
        try:
            from openpyxl import Workbook  # type: ignore

            # manejar list[dict]
            if isinstance(data, list) and data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [[row.get(h) for h in headers] for row in data]
            else:
                # intentar si es un "DataFrame-like" sin pandas: obtener atributos columns/values
                try:
                    headers = list(data.columns)
                    rows = data.values.tolist()
                except Exception:
                    # formato no soportado
                    return ""

            wb = Workbook()
            ws = wb.active
            ws.title = sheet_name
            # escribir cabeceras
            ws.append(headers)
            # escribir filas
            for r in rows:
                ws.append(r)
            wb.save(ruta)
            return str(ruta)
        except Exception as e:
            # si falla todo, devolver cadena vacía (y loguear)
            print(f"❌ Error exportando Excel: {e}")
            return ""
        
def set_window_icon(win):
    import sys
    from pathlib import Path
    try:
        base = (Path(sys.executable).parent
                if getattr(sys, "frozen", False)
                else Path(__file__).parent.parent)
        win.iconbitmap(str(base / "assets" / "icon.ico"))
    except Exception:
        pass


import os
from datetime import datetime

def export_sql_to_file(nombre_base, contenido, carpeta=None):
    if not contenido:
        return ""

    if carpeta is None:
        from config.constants import DIR_QUERY_SIG
        carpeta = str(DIR_QUERY_SIG)
    os.makedirs(carpeta, exist_ok=True)

    fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nombre_archivo = f"{nombre_base}_{fecha_hora}.txt"

    ruta = os.path.join(carpeta, nombre_archivo)

    with open(ruta, "w", encoding="utf-8") as f:
        for linea in contenido:
            f.write(linea + "\n")

    return ruta