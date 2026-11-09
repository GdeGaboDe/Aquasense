"""API para el nodo autónomo: /api/v1/device/* (CLAUDE.md, sección 6)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.api.deps import AutonomoActual, SesionBD, exigir_red_local
from app.esquemas.control import Ack, RespuestaAck, RespuestaConfig
from app.esquemas.dispositivo import LoteTelemetria, RespuestaTelemetria
from app.servicios import dispositivo as servicio
from app.servicios.ingesta import ingerir_lote

router = APIRouter(
    prefix="/api/v1/device",
    tags=["dispositivo"],
    dependencies=[Depends(exigir_red_local)],
)


@router.post("/telemetry", response_model=RespuestaTelemetria)
def recibir_telemetria(
    lote: LoteTelemetria, autonomo: AutonomoActual, sesion: SesionBD
) -> RespuestaTelemetria:
    return ingerir_lote(sesion, autonomo, lote, datetime.now(UTC))


@router.get("/config", response_model=RespuestaConfig)
def entregar_config(autonomo: AutonomoActual, sesion: SesionBD) -> RespuestaConfig:
    return servicio.obtener_config(sesion, autonomo, datetime.now(UTC))


@router.post("/ack", response_model=RespuestaAck)
def recibir_ack(ack: Ack, autonomo: AutonomoActual, sesion: SesionBD) -> RespuestaAck:
    return servicio.registrar_ack(sesion, autonomo, ack, datetime.now(UTC))
