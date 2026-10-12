# Sistema de Reservas — FastAPI + MongoDB Atlas + Concurrencia

Aplicación web full-stack para gestionar reservas de restaurante, con
persistencia en la nube, validación estricta y procesamiento pesado
de CPU sin bloquear el servidor.

## Características

| Requisito | Implementación |
|---|---|
| API REST | FastAPI + Pydantic v2 (6 endpoints) |
| Base de datos | MongoDB Atlas vía **Motor** (async) |
| Ciclo de vida | `@asynccontextmanager` (`lifespan`) |
| Concurrencia | `asyncio.to_thread()` en `/api/reportes/ocupacion` |
| Frontend | HTML5 + JS Vanilla con `fetch()` y `StaticFiles` |
| Configuración | `pydantic-settings` + `.env` |

## Estructura

```
app/
├── main.py           # App FastAPI + StaticFiles + CORS
├── config.py         # Settings con pydantic-settings
├── database.py       # Cliente Motor + lifespan
├── schemas.py        # Modelos Pydantic
└── routers/
    ├── reservas.py   # CRUD
    └── reportes.py   # Tarea CPU-bound con to_thread
static/               # Frontend
```

## Instalación

### 1. Clonar y crear entorno virtual

```bash
git clone <tu-repo>.git
cd reservas-app

python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar MongoDB Atlas

1. Crea una cuenta en <https://www.mongodb.com/cloud/atlas> y un **cluster gratuito (M0)**.
2. En **Database Access**, crea un usuario con contraseña.
3. En **Network Access**, agrega `0.0.0.0/0` (solo para desarrollo).
4. Copia la cadena de conexión (*Connect → Drivers*).

### 4. Variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y pega tu URI:

```env
MONGODB_URI=mongodb+srv://usuario:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB=reservas_db
APP_NAME=Sistema de Reservas
DEBUG=false
```

### 5. Ejecutar

```bash
uvicorn app.main:app --reload --port 8000
```

- Frontend → <http://localhost:8000>
- Swagger UI → <http://localhost:8000/docs>
- ReDoc → <http://localhost:8000/redoc>

## Endpoints

| Método | Ruta | Descripción | Códigos |
|---|---|---|---|
| `POST` | `/api/reservas` | Crear reserva | `201`, `400`, `409`, `422` |
| `GET` | `/api/reservas` | Listar con filtros y paginación | `200` |
| `GET` | `/api/reservas/{id}` | Obtener una reserva | `200`, `400`, `404` |
| `PUT` | `/api/reservas/{id}` | Actualizar reserva | `200`, `400`, `404`, `409`, `422` |
| `DELETE` | `/api/reservas/{id}` | Eliminar reserva | `204`, `400`, `404` |
| `POST` | `/api/reportes/ocupacion` | Reporte pesado (no bloqueante) | `200`, `422` |
| `GET` | `/api/reportes/health` | Ping ligero | `200` |

### Ejemplo: crear reserva

```bash
curl -X POST http://localhost:8000/api/reservas \
  -H "Content-Type: application/json" \
  -d '{
    "cliente_nombre": "Ana Torres",
    "cliente_email": "ana@example.com",
    "telefono": "+52 555 123 4567",
    "fecha": "2026-01-20",
    "hora": "20:00",
    "num_personas": 4,
    "mesa": "M5",
    "notas": "Cumpleaños"
  }'
```

### Ejemplo: reporte pesado

```bash
curl -X POST http://localhost:8000/api/reportes/ocupacion \
  -H "Content-Type: application/json" \
  -d '{"iteraciones": 8000000}'
```

## Prueba de concurrencia

**Opción A — desde el frontend**
1. Abre <http://localhost:8000>.
2. Presiona ** Probar concurrencia**.
3. El panel mostrará en tiempo real los `ping` al endpoint `/api/health`
   mientras el reporte se procesa en un hilo aparte. Verás que las
   latencias se mantienen bajas (~5-30 ms).

**Opción B — desde la terminal**

Terminal 1:
```bash
curl -X POST http://localhost:8000/api/reportes/ocupacion \
  -H "Content-Type: application/json" \
  -d '{"iteraciones": 20000000}'
```

Terminal 2 (mientras corre lo anterior):
```bash
for i in {1..20}; do
  curl -s -o /dev/null -w "ping $i → %{http_code} en %{time_total}s\n" \
    http://localhost:8000/api/health
  sleep 0.4
done
```

Si el servidor **responde con normalidad durante todo el proceso**,
la concurrencia está bien implementada. Si hubiera usado una función
bloqueante directamente en el `async def`, los pings se congelarían
hasta terminar el reporte.

## ¿Por qué `asyncio.to_thread()`?

`asyncio` es cooperativo y de un solo hilo: si dentro de un `async def`
ejecutas código CPU-bound, **bloqueas el event loop completo** y ninguna
otra petición se atiende. `asyncio.to_thread()` mueve esa función a un
hilo del `ThreadPoolExecutor`, dejando el event loop libre para seguir
atendiendo requests. En la respuesta se incluye `hilo_ejecucion` vs
`hilo_principal` para evidenciarlo.

## Tecnologías

- **FastAPI** 0.115 — framework web async
- **Pydantic** 2.9 — validación estricta
- **Motor** 3.6 — driver async de MongoDB
- **MongoDB Atlas** — base de datos en la nube
- **Uvicorn** — servidor ASGI
- **JS Vanilla** — sin frameworks en el frontend