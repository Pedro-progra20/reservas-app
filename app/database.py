"""
Gestión del ciclo de vida global de la aplicación y conexión asíncrona
a MongoDB Atlas mediante Motor.

Se utiliza @asynccontextmanager (lifespan) para abrir y cerrar el cliente
una sola vez durante toda la vida del proceso.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings


class MongoDBState:
    """Contenedor del estado global de la conexión."""

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


mongodb = MongoDBState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Abre la conexión al iniciar y la cierra al apagar la app."""

    mongodb.client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=8000,
        uuidRepresentation="standard",
    )
    mongodb.db = mongodb.client[settings.mongodb_db]

    # Verificación real de conectividad (falla rápido si la URI es inválida)
    await mongodb.client.admin.command("ping")

    # Índices útiles para las consultas más frecuentes
    await mongodb.db.reservas.create_index("fecha")
    await mongodb.db.reservas.create_index([("fecha", 1), ("hora", 1)])
    await mongodb.db.reservas.create_index("cliente_email")

    print(f"✅ Conectado a MongoDB Atlas → base de datos: {settings.mongodb_db}")

    try:
        yield
    finally:
        mongodb.client.close()
        print("🔌 Conexión a MongoDB cerrada correctamente")


def get_collection():
    """Devuelve la colección de reservas (o lanza si no hay conexión)."""
    if mongodb.db is None:
        raise RuntimeError("La base de datos no está inicializada")
    return mongodb.db.reservas