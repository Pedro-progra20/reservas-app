"""
Aplicación FastAPI: Sistema de Reservas.

Integra:
  • Persistencia en MongoDB Atlas (Motor, async)
  • Ciclo de vida global con @asynccontextmanager (lifespan)
  • Validación estricta con Pydantic v2
  • Concurrencia no bloqueante con asyncio.to_thread()
  • Frontend estático servido con StaticFiles
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import lifespan
from app.routers import reportes, reservas

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title=settings.app_name,
    description="API REST para gestión de reservas con reportes concurrentes.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(reservas.router)
app.include_router(reportes.router)

# Frontend estático
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", tags=["Health"])
async def health_root():
    return {"status": "ok", "app": settings.app_name}