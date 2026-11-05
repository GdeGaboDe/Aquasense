"""Tanques y su estado actual: /api/v1/tanques."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status

from app.api.deps import SesionBD, UsuarioSesion, obtener_usuario_actual
from app.api.seguridad import limitar_api_web
from app.esquemas.web import TanqueCrear, TanqueEditar, TanqueEstado, TanqueSalida
from app.modelos import Tanque
from app.servicios import instalacion as servicio

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
