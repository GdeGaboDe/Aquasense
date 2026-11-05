"""Dependencias compartidas de la capa HTTP."""

import hashlib
import ipaddress
import secrets
import time
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.config import obtener_settings
from app.db import obtener_fabrica_sesiones
from app.modelos import Nodo, Usuario
from app.repositorios.ingesta import buscar_autonomo_por_token
from app.servicios.errores import ErrorDeNegocio

_HEADERS_DE_PROXY = ("cf-connecting-ip", "x-forwarded-for")


def obtener_sesion() -> Iterator[Session]:
    with obtener_fabrica_sesiones()() as sesion:
        yield sesion


SesionBD = Annotated[Session, Depends(obtener_sesion)]


def _es_ip_privada(host: str | None) -> bool:
    try:
        return host is not None and ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def exigir_red_local(request: Request) -> None:
    """La API del dispositivo solo acepta la red local, nunca lo que llega por el túnel."""
    if not obtener_settings().dispositivo_solo_lan:
        return
    viene_de_proxy = any(header in request.headers for header in _HEADERS_DE_PROXY)
    host = request.client.host if request.client else None
    if viene_de_proxy or not _es_ip_privada(host):
        raise ErrorDeNegocio(
            status.HTTP_403_FORBIDDEN,
            "SOLO_RED_LOCAL",
            "Esta API solo acepta peticiones desde la red local.",
        )


def obtener_autonomo(
    sesion: SesionBD,
    token: Annotated[str | None, Header(alias="X-API-Token")] = None,
) -> Nodo:
    error = ErrorDeNegocio(
        status.HTTP_401_UNAUTHORIZED, "TOKEN_INVALIDO", "Falta el token o no es válido."
    )
    if not token:
        raise error
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    autonomo = buscar_autonomo_por_token(sesion, token_hash)
    if (
        autonomo is None
        or autonomo.token_hash is None
        or not secrets.compare_digest(autonomo.token_hash, token_hash)
        or not autonomo.activo
    ):
        raise error
    return autonomo


AutonomoActual = Annotated[Nodo, Depends(obtener_autonomo)]


def obtener_usuario_actual(request: Request, sesion: SesionBD) -> Usuario:
    error = ErrorDeNegocio(
        status.HTTP_401_UNAUTHORIZED, "SESION_REQUERIDA", "Inicia sesión para continuar."
    )
    datos = request.session
    usuario_id = datos.get("usuario_id")
    if usuario_id is None:
        raise error
    # SessionMiddleware renueva la cookie en cada respuesta; el límite de 8 h se cuenta aquí.
    limite_s = obtener_settings().sesion_horas * 3600
    usuario = sesion.get(Usuario, usuario_id)
    if (
        usuario is None
        or datos.get("version") != usuario.sesion_version
        or time.time() - datos.get("iniciada_en", 0) > limite_s
    ):
        datos.clear()
        raise error
    return usuario


UsuarioSesion = Annotated[Usuario, Depends(obtener_usuario_actual)]
