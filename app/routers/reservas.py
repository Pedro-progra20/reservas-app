"""
Endpoints CRUD para el recurso 'reservas'.
Códigos HTTP semánticos: 200, 201, 204, 400, 404, 409, 422.
"""

from datetime import date, datetime, time, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, status

from app.database import get_collection
from app.schemas import (
    ReservaCreate,
    ReservaListResponse,
    ReservaOut,
    ReservaUpdate,
)

router = APIRouter(prefix="/api/reservas", tags=["Reservas"])


# ──────────────────────── Helpers ────────────────────────

def _object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El id '{id_str}' no es un ObjectId válido",
        )


def _normalizar_fechas(data: dict) -> dict:
    """Convierte date/time a string para almacenarlos en Mongo."""
    if isinstance(data.get("fecha"), date):
        data["fecha"] = data["fecha"].isoformat()
    if isinstance(data.get("hora"), time):
        data["hora"] = data["hora"].strftime("%H:%M")
    return data


def _serializar(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


async def _verificar_disponibilidad(
    fecha: str, hora: str, mesa: str | None, excluir_id: ObjectId | None = None
) -> None:
    """
    Regla de negocio: no puede haber dos reservas activas
    en la misma mesa, misma fecha y misma hora.
    """
    if not mesa:
        return

    filtro = {
        "fecha": fecha,
        "hora": hora,
        "mesa": mesa,
        "estado": {"$ne": "cancelada"},
    }
    if excluir_id is not None:
        filtro["_id"] = {"$ne": excluir_id}

    existente = await get_collection().find_one(filtro)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La mesa '{mesa}' ya está reservada para {fecha} a las {hora}",
        )


# ──────────────────────── CREATE ────────────────────────

@router.post(
    "",
    response_model=ReservaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva reserva",
)
async def crear_reserva(payload: ReservaCreate):
    data = _normalizar_fechas(payload.model_dump())
    await _verificar_disponibilidad(data["fecha"], data["hora"], data.get("mesa"))

    ahora = datetime.now(timezone.utc)
    data["created_at"] = ahora
    data["updated_at"] = ahora

    resultado = await get_collection().insert_one(data)
    creado = await get_collection().find_one({"_id": resultado.inserted_id})
    return _serializar(creado)


# ──────────────────────── READ (lista) ────────────────────────

@router.get(
    "",
    response_model=ReservaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar reservas con filtros y paginación",
)
async def listar_reservas(
    estado: str | None = Query(None, pattern="^(pendiente|confirmada|cancelada)$"),
    fecha: date | None = Query(None),
    cliente_email: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    filtro: dict = {}
    if estado:
        filtro["estado"] = estado
    if fecha:
        filtro["fecha"] = fecha.isoformat()
    if cliente_email:
        filtro["cliente_email"] = cliente_email.lower()

    coleccion = get_collection()
    total = await coleccion.count_documents(filtro)
    cursor = (
        coleccion.find(filtro)
        .sort([("fecha", 1), ("hora", 1)])
        .skip((page - 1) * limit)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)

    return ReservaListResponse(
        total=total,
        page=page,
        limit=limit,
        items=[_serializar(d) for d in docs],
    )


# ──────────────────────── READ (uno) ────────────────────────

@router.get(
    "/{reserva_id}",
    response_model=ReservaOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener una reserva por id",
)
async def obtener_reserva(reserva_id: str):
    doc = await get_collection().find_one({"_id": _object_id(reserva_id)})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe una reserva con id {reserva_id}",
        )
    return _serializar(doc)


# ──────────────────────── UPDATE ────────────────────────

@router.put(
    "/{reserva_id}",
    response_model=ReservaOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar una reserva existente",
)
async def actualizar_reserva(reserva_id: str, payload: ReservaUpdate):
    oid = _object_id(reserva_id)
    coleccion = get_collection()

    actual = await coleccion.find_one({"_id": oid})
    if not actual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe una reserva con id {reserva_id}",
        )

    cambios = _normalizar_fechas(payload.model_dump(exclude_unset=True))
    if not cambios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se envió ningún campo para actualizar",
        )

    # Validar colisión de mesa solo si cambia algo relevante
    fecha_final = cambios.get("fecha", actual["fecha"])
    hora_final = cambios.get("hora", actual["hora"])
    mesa_final = cambios.get("mesa", actual.get("mesa"))
    if any(k in cambios for k in ("fecha", "hora", "mesa")):
        await _verificar_disponibilidad(fecha_final, hora_final, mesa_final, excluir_id=oid)

    cambios["updated_at"] = datetime.now(timezone.utc)
    await coleccion.update_one({"_id": oid}, {"$set": cambios})

    actualizado = await coleccion.find_one({"_id": oid})
    return _serializar(actualizado)


# ──────────────────────── DELETE ────────────────────────

@router.delete(
    "/{reserva_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una reserva",
)
async def eliminar_reserva(reserva_id: str):
    resultado = await get_collection().delete_one({"_id": _object_id(reserva_id)})
    if resultado.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe una reserva con id {reserva_id}",
        )
    return None