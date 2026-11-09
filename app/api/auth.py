"""Sesión web: /api/v1/auth/*."""

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import SesionBD, UsuarioSesion
from app.api.seguridad import LIMITE_LOGIN, limitador, limitar_api_web
from app.config import obtener_settings
from app.esquemas.web import Credenciales, UsuarioActual
from app.servicios.autenticacion import autenticar, invalidar_sesiones

router = APIRouter(
    prefix="/api/v1/auth", tags=["autenticación"], dependencies=[Depends(limitar_api_web)]
)


def _usuario_actual(nombre: str) -> UsuarioActual:
    settings = obtener_settings()
    return UsuarioActual(
        usuario=nombre,
        polling_panel_s=settings.polling_panel_s,
        polling_graficas_s=settings.polling_graficas_s,
        polling_comando_s=settings.polling_comando_s,
        zona_horaria=settings.zona_horaria_web,
    )


@router.post("/login", response_model=UsuarioActual)
@limitador.limit(LIMITE_LOGIN)
def login(request: Request, credenciales: Credenciales, sesion: SesionBD) -> UsuarioActual:
    usuario = autenticar(sesion, credenciales.usuario, credenciales.contrasena, datetime.now(UTC))
    request.session.clear()
    request.session.update(
        usuario_id=usuario.id, version=usuario.sesion_version, iniciada_en=int(time.time())
    )
    return _usuario_actual(usuario.usuario)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, usuario: UsuarioSesion, sesion: SesionBD) -> Response:
    invalidar_sesiones(sesion, usuario)
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/yo", response_model=UsuarioActual)
def yo(usuario: UsuarioSesion) -> UsuarioActual:
    return _usuario_actual(usuario.usuario)
