"""API para el nodo autónomo: /api/v1/device/* (CLAUDE.md, sección 6)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.api.deps import AutonomoActual, SesionBD, exigir_red_local
from app.esquemas.dispositivo import LoteTelemetria, RespuestaTelemetria
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
