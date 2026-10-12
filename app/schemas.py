"""
Modelos Pydantic con validación estricta de entradas y salidas.
"""

from datetime import date, datetime, time, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

EstadoReserva = Literal["pendiente", "confirmada", "cancelada"]


# ─────────────────────────── ENTRADA ───────────────────────────

class ReservaBase(BaseModel):
    cliente_nombre: str = Field(
        ..., min_length=2, max_length=100,
        description="Nombre completo del cliente",
    )
    cliente_email: EmailStr = Field(..., description="Correo electrónico válido")
    telefono: str = Field(
        ..., pattern=r"^\+?[0-9\s\-]{7,20}$",
        description="Teléfono con 7 a 20 dígitos (permite +, espacios y guiones)",
    )
    fecha: date = Field(..., description="Fecha de la reserva (YYYY-MM-DD)")
    hora: time = Field(..., description="Hora de la reserva (HH:MM)")
    num_personas: int = Field(..., ge=1, le=20, description="Comensales (1-20)")
    mesa: Optional[str] = Field(None, max_length=10)
    notas: Optional[str] = Field(None, max_length=500)

    @field_validator("fecha")
    @classmethod
    def fecha_no_pasada(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("La fecha de la reserva no puede ser anterior a hoy")
        return v

    @field_validator("hora")
    @classmethod
    def horario_valido(cls, v: time) -> time:
        if not (time(11, 0) <= v <= time(23, 30)):
            raise ValueError("El horario de atención es de 11:00 a 23:30")
        return v

    @field_validator("cliente_nombre")
    @classmethod
    def nombre_limpio(cls, v: str) -> str:
        v = " ".join(v.split())
        if not all(c.isalpha() or c.isspace() or c in ".-'" for c in v):
            raise ValueError("El nombre solo puede contener letras y espacios")
        return v.title()


class ReservaCreate(ReservaBase):
    estado: EstadoReserva = "pendiente"


class ReservaUpdate(BaseModel):
    """Todos los campos opcionales: se aplica PATCH semántico sobre PUT."""

    cliente_nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    cliente_email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, pattern=r"^\+?[0-9\s\-]{7,20}$")
    fecha: Optional[date] = None
    hora: Optional[time] = None
    num_personas: Optional[int] = Field(None, ge=1, le=20)
    mesa: Optional[str] = Field(None, max_length=10)
    notas: Optional[str] = Field(None, max_length=500)
    estado: Optional[EstadoReserva] = None

    @field_validator("fecha")
    @classmethod
    def fecha_no_pasada(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v < date.today():
            raise ValueError("La fecha de la reserva no puede ser anterior a hoy")
        return v


# ─────────────────────────── SALIDA ───────────────────────────

class ReservaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cliente_nombre: str
    cliente_email: EmailStr
    telefono: str
    fecha: date
    hora: time
    num_personas: int
    mesa: Optional[str] = None
    notas: Optional[str] = None
    estado: EstadoReserva
    created_at: datetime
    updated_at: datetime


class ReservaListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[ReservaOut]


# ─────────────────────────── REPORTES ───────────────────────────

class ReporteRequest(BaseModel):
    """Parámetros del reporte pesado de ocupación."""

    iteraciones: int = Field(
        6_000_000,
        ge=500_000,
        le=40_000_000,
        description="Tamaño de la carga CPU (criba de primos). Más = más lento.",
    )
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    incluir_canceladas: bool = False

    @field_validator("fecha_hasta")
    @classmethod
    def rango_coherente(cls, v, info):
        desde = info.data.get("fecha_desde")
        if v and desde and v < desde:
            raise ValueError("fecha_hasta no puede ser menor que fecha_desde")
        return v


class ReporteResponse(BaseModel):
    resumen: dict
    ocupacion_por_dia: list[dict]
    ocupacion_por_hora: list[dict]
    top_mesas: list[dict]
    primos_encontrados: int
    tiempo_cpu_segundos: float
    tiempo_total_segundos: float
    hilo_ejecucion: str
    generado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))