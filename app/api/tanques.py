"""Tanques y su estado actual: /api/v1/tanques."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SesionBD, UsuarioSesion, obtener_usuario_actual
from app.api.seguridad import limitar_api_web
from app.esquemas.control import (
    MAX_POR_PAGINA,
    DosisSalida,
    Pagina,
    UmbralesEditar,
    UmbralSalida,
)
from app.esquemas.web import TanqueCrear, TanqueEditar, TanqueEstado, TanqueSalida
from app.modelos import Tanque
from app.servicios import dosis as servicio_dosis
from app.servicios import instalacion as servicio
from app.servicios import umbrales as servicio_umbrales

router = APIRouter(
    prefix="/api/v1/tanques",
    tags=["tanques"],
    dependencies=[Depends(limitar_api_web), Depends(obtener_usuario_actual)],
)


@router.get("", response_model=list[TanqueEstado])
def listar(sesion: SesionBD) -> list[TanqueEstado]:
    return servicio.estado_de_tanques(sesion, datetime.now(UTC))


@router.post("", response_model=TanqueSalida, status_code=status.HTTP_201_CREATED)
def crear(datos: TanqueCrear, usuario: UsuarioSesion, sesion: SesionBD) -> Tanque:
    return servicio.crear_tanque(sesion, datos, usuario.id, datetime.now(UTC))


@router.patch("/{tanque_id}", response_model=TanqueSalida)
def editar(tanque_id: int, datos: TanqueEditar, sesion: SesionBD) -> Tanque:
    return servicio.editar_tanque(sesion, tanque_id, datos)


@router.get("/{tanque_id}/umbrales", response_model=list[UmbralSalida])
def obtener_umbrales(tanque_id: int, sesion: SesionBD) -> list[UmbralSalida]:
    return servicio_umbrales.obtener(sesion, tanque_id)


@router.put("/{tanque_id}/umbrales", response_model=list[UmbralSalida])
def actualizar_umbrales(
    tanque_id: int, datos: UmbralesEditar, sesion: SesionBD
) -> list[UmbralSalida]:
    return servicio_umbrales.actualizar(sesion, tanque_id, datos)


@router.get("/{tanque_id}/dosis", response_model=Pagina[DosisSalida])
def listar_dosis(
    tanque_id: int,
    sesion: SesionBD,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamano: Annotated[int, Query(ge=1, le=MAX_POR_PAGINA)] = 20,
) -> Pagina[DosisSalida]:
    return servicio_dosis.listar(sesion, tanque_id, pagina, tamano)
