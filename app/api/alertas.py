"""Alertas: /api/v1/alertas."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SesionBD, obtener_usuario_actual
from app.api.seguridad import limitar_api_web
from app.esquemas.control import MAX_POR_PAGINA, AlertaSalida, Pagina
from app.servicios import alertas as servicio

router = APIRouter(
    prefix="/api/v1/alertas",
    tags=["alertas"],
    dependencies=[Depends(limitar_api_web), Depends(obtener_usuario_actual)],
)


@router.get("", response_model=Pagina[AlertaSalida])
def listar(
    sesion: SesionBD,
    activa: bool | None = None,
    tanque_id: Annotated[int | None, Query(ge=1)] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano: Annotated[int, Query(ge=1, le=MAX_POR_PAGINA)] = 20,
) -> Pagina[AlertaSalida]:
    return servicio.listar(sesion, activa, tanque_id, pagina, tamano)
