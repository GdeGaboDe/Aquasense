"""Cuentas de administrador y verificación de credenciales."""

from datetime import datetime
from functools import lru_cache

import bcrypt
from fastapi import status
from sqlalchemy.orm import Session

from app.modelos import Usuario
from app.repositorios import instalacion as repo
from app.servicios.errores import ErrorDeNegocio

LONGITUD_MINIMA_CONTRASENA = 12
# bcrypt solo admite 72 bytes; con más, la versión 5 lanza un error en lugar de truncar.
_MAX_BYTES_BCRYPT = 72


def validar_contrasena_nueva(contrasena: str) -> None:
    if len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
        raise ValueError(
            f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres."
        )
    if len(contrasena.encode()) > _MAX_BYTES_BCRYPT:
        raise ValueError(f"La contraseña no puede pasar de {_MAX_BYTES_BCRYPT} bytes.")


def crear_usuario(sesion: Session, nombre: str, contrasena: str, ahora: datetime) -> Usuario:
    validar_contrasena_nueva(contrasena)
    if repo.buscar_usuario(sesion, nombre) is not None:
        raise ValueError(f"El usuario {nombre} ya existe.")
    usuario = Usuario(
        usuario=nombre,
        hash_contrasena=bcrypt.hashpw(contrasena.encode(), bcrypt.gensalt()).decode(),
        creado_en=ahora,
    )
    sesion.add(usuario)
    sesion.commit()
    return usuario


@lru_cache
def _hash_de_relleno() -> bytes:
    return bcrypt.hashpw(b"relleno", bcrypt.gensalt())


def _contrasena_correcta(contrasena: str, hash_guardado: str | None) -> bool:
    bytes_contrasena = contrasena.encode()
    if len(bytes_contrasena) > _MAX_BYTES_BCRYPT:
        bytes_contrasena = bytes_contrasena[:_MAX_BYTES_BCRYPT]
        hash_guardado = None
    # Con usuario inexistente también se calcula un hash: la demora no revela si el usuario existe.
    objetivo = hash_guardado.encode() if hash_guardado else _hash_de_relleno()
    return bcrypt.checkpw(bytes_contrasena, objetivo) and hash_guardado is not None


def autenticar(sesion: Session, nombre: str, contrasena: str, ahora: datetime) -> Usuario:
    usuario = repo.buscar_usuario(sesion, nombre)
    guardado = usuario.hash_contrasena if usuario else None
    if usuario is None or not _contrasena_correcta(contrasena, guardado):
        raise ErrorDeNegocio(
            status.HTTP_401_UNAUTHORIZED,
            "CREDENCIALES_INVALIDAS",
            "Usuario o contraseña incorrectos.",
        )
    usuario.ultimo_acceso = ahora
    sesion.commit()
    return usuario


def invalidar_sesiones(sesion: Session, usuario: Usuario) -> None:
    usuario.sesion_version += 1
    sesion.commit()
