"""Contratos de la API de la aplicación web."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

from app.esquemas.dispositivo import Mac


def _iso_utc(momento: datetime) -> str:
    """ISO 8601 UTC con milisegundos: 2026-11-20T15:04:05.123Z (CLAUDE.md, 8.2)."""
    return momento.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


FechaIso = Annotated[datetime, PlainSerializer(_iso_utc, return_type=str)]
Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
TextoLibre = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Volumen = Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)]


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=60)
    contrasena: str = Field(min_length=1, max_length=128)


class UsuarioActual(BaseModel):
    usuario: str
    polling_panel_s: int
    polling_graficas_s: int
    polling_comando_s: int
    zona_horaria: str


class TanqueCrear(BaseModel):
    nombre: Nombre
    volumen_l: Volumen
    especie: Nombre | None = None
    notas: TextoLibre | None = None


class TanqueEditar(BaseModel):
    nombre: Nombre | None = None
    volumen_l: Volumen | None = None
    especie: Nombre | None = None
    notas: TextoLibre | None = None

    @model_validator(mode="after")
    def _obligatorios_no_nulos(self) -> Self:
        for campo in ("nombre", "volumen_l"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser nulo")
        return self


class TanqueSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    volumen_l: float
    especie: str | None
    notas: str | None


class LecturaActual(BaseModel):
    variable: str
    nombre: str
    unidad: str | None
    tipo: Literal["numero", "booleano"]
    valor: float
    medido_en: FechaIso


class NodoResumen(BaseModel):
    id: int
    nombre: str
    mac: str
    es_satelite: bool
    activo: bool
    firmware: str | None
    ultimo_contacto: FechaIso | None
    modulos: list[str]


class AlertaActiva(BaseModel):
    id: int
    tipo: str
    descripcion: str
    severidad: Literal["info", "advertencia", "critica"]
    variable_nombre: str | None
    unidad: str | None
    valor: float | None
    iniciada_en: FechaIso


class TanqueEstado(TanqueSalida):
    estado: Literal["en_linea", "sin_conexion", "sin_nodo"]
    nodo: NodoResumen | None
    lecturas: list[LecturaActual]
    alertas: list[AlertaActiva]


class NodoCrear(BaseModel):
    mac: Mac
    nombre: Nombre
    tanque_id: int = Field(ge=1)
    padre_id: int | None = Field(default=None, ge=1)


class NodoEditar(BaseModel):
    nombre: Nombre | None = None
    activo: bool | None = None

    @model_validator(mode="after")
    def _sin_nulos(self) -> Self:
        for campo in self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser nulo")
        return self


class NodoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mac: str
    nombre: str
    tanque_id: int
    padre_id: int | None
    activo: bool


class NodoCreado(NodoSalida):
    token: str | None = Field(description="Solo se muestra esta vez. Los satélites no tienen.")
