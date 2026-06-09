# SincroSIG

Herramienta de escritorio para sincronización de datos entre el sistema de tiendas **SIG** y la plataforma central **SAP Business One / SGCONTA**, con módulo de reconciliación de stock.

---

## Funcionalidades

### SGCONTA — Sincronización de maestros
| Módulo | Descripción |
|---|---|
| Personal | Sincroniza empleados desde SIG a SGCONTA |
| Estado Personal | Actualiza estados de empleados |
| Tiendas | Sincroniza catálogo de tiendas |
| Tienda Personal | Asigna personal a tiendas |
| Detalle Cargo | Sincroniza detalle de cargos |
| Cargo Personal | Asigna cargos a empleados |

### Formulaciones
- **Verificar Formulación TDA vs SIG** — valida diferencias entre formulaciones de tienda y SIG
- **Reporte Comparativo de Formulaciones** — genera reporte Excel con comparativa

### Ajustes SAP — Reconciliación de Stock
Calcula los ingresos necesarios en SAP para regularizar diferencias de stock originadas por salidas fallidas en el proceso de migración SIG→SAP.

Produce dos tipos de ajuste:
- **NIVELACIÓN** *(amarillo)* — el stock SIG es mayor al stock SAP; se debe ingresar la diferencia
- **COLA Primaria** *(verde)* — salida fallida cuyo ítem figura como primario en el campo `message` de `log_transfer_sunsap`
- **COLA Secundaria** *(naranja)* — salidas fallidas del mismo documento que el ítem primario (líneas anteriores/posteriores)

---

## Requisitos

- Python 3.10+
- Dependencias:

```
pip install ttkbootstrap mysql-connector-python pandas xlsxwriter python-dotenv
```

---

## Configuración

1. Copia el archivo de ejemplo y completa con las credenciales reales:

```bash
cp .env.example .env
```

2. Edita `.env` con los datos de conexión:

```env
SIG_HOST=servidor_sig
SIG_USER=usuario
SIG_PASS=contraseña
SIG_DB=nombre_bd

WEB_HOST=servidor_sgconta
WEB_USER=usuario
WEB_PASS=contraseña
WEB_DB=nombre_bd

TIENDA_3_HOST=192.168.3.99
TIENDA_3_USER=helpdesk
TIENDA_3_PASS=...
TIENDA_3_DB=nombre_bd
# ... una sección por cada tienda
```

---

## Ejecución

```bash
python app.py
```

---

## Estructura del proyecto

```
SincroSIG/
├── app.py                          # Punto de entrada
├── .env                            # Credenciales (NO subir a git)
├── .env.example                    # Plantilla de configuración
├── config/
│   ├── db.py                       # Conexiones MySQL (SIG, WEB, tiendas)
│   ├── settings.py                 # Carga de variables de entorno
│   └── utils.py                    # Utilidades compartidas
├── gui/
│   ├── main_window.py              # Ventana principal
│   ├── progress_window.py          # Ventana de progreso
│   └── searchable_checklist.py     # Componente selector de tiendas
├── controllers/
│   ├── reconciliacion_controller.py  # UI y lógica de Reconciliación SAP
│   ├── sync_controller.py            # UI de sincronizaciones SGCONTA
│   ├── formulaciones_controller.py   # UI de formulaciones
│   └── validacion_controller.py      # UI de validaciones
├── modules/
│   ├── reconciliacion_sap_service.py # Cálculo NIVELACIÓN + COLA
│   ├── sync_tiendas.py               # Sincronización de tiendas
│   ├── sync_personal.py              # Sincronización de personal
│   ├── formulaciones_service.py      # Lógica de formulaciones
│   └── ...                           # Demás servicios
└── logs/                           # Logs operativos (NO subir a git)
```

---

## Lógica de Reconciliación SAP

```
Para cada (ItemCode, WhsCode) con salidas fallidas en log_transfer_sunsap:

1. NIVELACIÓN:  si Stock_SIG > Stock_SAP → ingresar diferencia
2. COLA:        simular cada salida fallida en orden cronológico
                si stock simulado < cantidad salida → ingresar faltante
```

El campo `message` de `log_transfer_sunsap` contiene el índice de la línea fallida (`[line: N]`). Esa línea es el ítem **primario**; las demás líneas del mismo documento son **secundarias**.

---

## Seguridad

El archivo `.env` contiene credenciales de producción. Está incluido en `.gitignore` y **nunca debe subirse al repositorio**.
