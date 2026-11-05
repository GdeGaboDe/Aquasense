"""Contrato de telemetría con el ESP32 (CLAUDE.md, 6.1)."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

MAX_NODOS_POR_LOTE = 50
# Tope generoso: el reenvío desde LittleFS puede acumular horas de lecturas.
MAX_LECTURAS_POR_LOTE = 5000
MAX_EVENTOS_POR_LOTE = 1000

Mac = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$"),
    AfterValidator(str.upper),
]
EpochMs = Annotated[int, Field(ge=0)]
EdadMs = Annotated[int, Field(ge=0)]
Boot = Annotated[int, Field(ge=0, le=2_147_483_647)]


class NodoReportado(BaseModel):
    mac: Mac
    firmware: str | None = Field(default=None, max_length=20)
    boot: Boot
    modulos: list[Annotated[str, Field(max_length=20)]] = Field(max_length=30)
    config_version_aplicada: int | None = Field(default=None, ge=0, le=2_147_483_647)


class LecturaReportada(BaseModel):
    mac: Mac
    variable: str = Field(max_length=40)
    # DECIMAL(10,3) admite hasta 7 enteros; rechazar aquí evita un error al insertar.
    valor: float = Field(allow_inf_nan=False, gt=-10_000_000, lt=10_000_000)
    edad_ms: EdadMs
    boot: Boot
    epoch_ms: EpochMs | None = None


class EventoDosis(BaseModel):
    mac: Mac
    tipo: Literal["dosis"]
    cargas: int = Field(ge=1, le=5)
    origen: Literal["remoto", "automatico", "local"]
    comando_id: int | None = Field(default=None, ge=1)
    edad_ms: EdadMs
    boot: Boot
    epoch_ms: EpochMs | None = None


class LoteTelemetria(BaseModel):
    lote: int = Field(ge=0)
    enviado_epoch_ms: EpochMs | None = None
    nodos: list[NodoReportado] = Field(max_length=MAX_NODOS_POR_LOTE)
    lecturas: list[LecturaReportada] = Field(default=[], max_length=MAX_LECTURAS_POR_LOTE)
    eventos: list[EventoDosis] = Field(default=[], max_length=MAX_EVENTOS_POR_LOTE)


class Rechazo(BaseModel):
    lista: Literal["lecturas", "eventos"]
    indice: int
    motivo: str


class RespuestaTelemetria(BaseModel):
    aceptadas: int
    duplicadas: int
    rechazadas: list[Rechazo]
