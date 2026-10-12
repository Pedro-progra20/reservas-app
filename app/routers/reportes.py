"""
Endpoint de reporte pesado. La tarea intensiva de CPU (criba de Eratóstenes
+ agregaciones) se delega a un hilo secundario con asyncio.to_thread()
para NO bloquear el event loop de FastAPI.
"""

import asyncio
import threading
import time
from collections import Counter, defaultdict

from fastapi import APIRouter, status

from app.database import get_collection
from app.schemas import ReporteRequest, ReporteResponse

router = APIRouter(prefix="/api/reportes", tags=["Reportes"])


# ─────────────── TAREA BLOQUEANTE (CPU-BOUND) ───────────────
def _criba_primos(limite: int) -> int:
    """Criba de Eratóstenes: trabajo puramente CPU-bound, sin I/O."""
    if limite < 2:
        return 0
    criba = bytearray([1]) * (limite + 1)
    criba[0] = criba[1] = 0
    for i in range(2, int(limite ** 0.5) + 1):
        if criba[i]:
            paso = i
            inicio = i * i
            criba[inicio::paso] = b"\x00" * len(range(inicio, limite + 1, paso))
    return sum(criba)


def _calcular_reporte(reservas: list[dict], iteraciones: int) -> dict:
    """
    Función SÍNCRONA y bloqueante. Se ejecuta dentro de un hilo
    secundario gracias a asyncio.to_thread().
    """
    t0 = time.perf_counter()

    # 1) Carga CPU artificial pero real (bloquea el hilo ~2-6 s)
    primos = _criba_primos(iteraciones)

    # 2) Agregaciones reales sobre los datos de Mongo
    por_dia: dict[str, dict] = defaultdict(lambda: {"reservas": 0, "personas": 0})
    por_hora: dict[str, int] = defaultdict(int)
    por_mesa: Counter = Counter()
    total_personas = 0
    total_reservas = len(reservas)

    for r in reservas:
        personas = r.get("num_personas", 0)
        total_personas += personas

        dia = r.get("fecha", "sin-fecha")
        por_dia[dia]["reservas"] += 1
        por_dia[dia]["personas"] += personas

        hora = r.get("hora", "??:??")
        por_hora[hora] += personas

        if r.get("mesa"):
            por_mesa[r["mesa"]] += 1

    # 3) Un poco más de trabajo CPU para que se note
    acumulador = 0.0
    for i in range(iteraciones // 10):
        acumulador += (i % 13) * 0.001

    tiempo_cpu = time.perf_counter() - t0

    return {
        "resumen": {
            "total_reservas": total_reservas,
            "total_personas": total_personas,
            "promedio_personas": round(total_personas / total_reservas, 2)
            if total_reservas else 0,
            "chequeo_interno": round(acumulador, 3),
        },
        "ocupacion_por_dia": [
            {"fecha": k, **v} for k, v in sorted(por_dia.items())
        ],
        "ocupacion_por_hora": [
            {"hora": k, "personas": v} for k, v in sorted(por_hora.items())
        ],
        "top_mesas": [
            {"mesa": m, "reservas": c} for m, c in por_mesa.most_common(5)
        ],
        "primos_encontrados": primos,
        "tiempo_cpu_segundos": round(tiempo_cpu, 3),
        "hilo_ejecucion": threading.current_thread().name,
    }


# ─────────────── ENDPOINT ASÍNCRONO ───────────────
@router.post(
    "/ocupacion",
    response_model=ReporteResponse,
    status_code=status.HTTP_200_OK,
    summary="Generar reporte pesado de ocupación (no bloquea el event loop)",
)
async def generar_reporte_ocupacion(payload: ReporteRequest):
    t_inicio = time.perf_counter()

    filtro: dict = {}
    if not payload.incluir_canceladas:
        filtro["estado"] = {"$ne": "cancelada"}
    if payload.fecha_desde or payload.fecha_hasta:
        rango: dict = {}
        if payload.fecha_desde:
            rango["$gte"] = payload.fecha_desde.isoformat()
        if payload.fecha_hasta:
            rango["$lte"] = payload.fecha_hasta.isoformat()
        filtro["fecha"] = rango

    # I/O asíncrono: no bloquea
    docs = await get_collection().find(filtro).to_list(length=None)

    # CPU-bound delegado a un hilo → el event loop sigue libre
    resultado = await asyncio.to_thread(_calcular_reporte, docs, payload.iteraciones)

    resultado["tiempo_total_segundos"] = round(time.perf_counter() - t_inicio, 3)
    resultado["hilo_principal"] = threading.current_thread().name
    return resultado


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Ping ligero para demostrar que el servidor sigue vivo",
)
async def health():
    return {
        "status": "ok",
        "hilo": threading.current_thread().name,
        "timestamp": time.time(),
    }