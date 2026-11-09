"""Comandos remotos: /api/v1/comandos."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SesionBD, UsuarioSesion, obtener_usuario_actual
from app.api.seguridad import limitar_api_web
from app.esquemas.control import MAX_POR_PAGINA, ComandoCrear, ComandoSalida, Pagina
from app.servicios import comandos as servicio

router = APIRouter(
    prefix="/api/v1/comandos",
    tags=["comandos"],
    dependencies=[Depends(limitar_api_web), Depends(obtener_usuario_actual)],
)


@router.post("", response_model=ComandoSalida, status_code=status.HTTP_201_CREATED)
def crear(datos: ComandoCrear, usuario: UsuarioSesion, sesion: SesionBD) -> ComandoSalida:
    return servicio.crear(sesion, datos, usuario, datetime.now(UTC))


@router.get("", response_model=Pagina[ComandoSalida])
def listar(
    sesion: SesionBD,
    nodo_id: Annotated[int | None, Query(ge=1)] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano: Annotated[int, Query(ge=1, le=MAX_POR_PAGINA)] = 20,
) -> Pagina[ComandoSalida]:
    return servicio.listar(sesion, nodo_id, pagina, tamano, datetime.now(UTC))
