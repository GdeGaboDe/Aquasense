"""Alta y edición de tanques y nodos, y estado actual de cada tanque."""

import hashlib
import secrets
from datetime import datetime
from decimal import Decimal

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dominio.conexion import esta_sin_conexion
from app.esquemas.web import (
    LecturaActual,
    NodoCrear,
    NodoEditar,
    NodoResumen,
    TanqueCrear,
    TanqueEditar,
    TanqueEstado,
    TanqueSalida,
)
from app.modelos import CambioAgua, Nodo, Tanque
from app.repositorios import instalacion as repo
from app.servicios.errores import ErrorDeNegocio

_BYTES_TOKEN = 30  # token_urlsafe produce 40 caracteres con 30 bytes
_PORCENTAJE_LLENADO = Decimal(100)


def _no_encontrado(recurso: str) -> ErrorDeNegocio:
    return ErrorDeNegocio(
        status.HTTP_404_NOT_FOUND, f"{recurso.upper()}_NO_ENCONTRADO", f"No existe ese {recurso}."
    )


def _guardar(sesion: Session, code: str, message: str) -> None:
    try:
        sesion.commit()
    except IntegrityError as error:
        sesion.rollback()
        raise ErrorDeNegocio(status.HTTP_409_CONFLICT, code, message) from error


def crear_tanque(sesion: Session, datos: TanqueCrear, usuario_id: int, ahora: datetime) -> Tanque:
    """Da de alta el tanque y registra su llenado como primer cambio de agua."""
    tanque = Tanque(**datos.model_dump())
    sesion.add(tanque)
    try:
        sesion.flush()
    except IntegrityError as error:
        sesion.rollback()
        raise ErrorDeNegocio(
            status.HTTP_409_CONFLICT, "TANQUE_DUPLICADO", "Ya existe un tanque con ese nombre."
        ) from error
    sesion.add(
        CambioAgua(
            tanque_id=tanque.id,
            realizado_en=ahora,
            porcentaje=_PORCENTAJE_LLENADO,
            registrado_por=usuario_id,
        )
    )
    sesion.commit()
    return tanque


def editar_tanque(sesion: Session, tanque_id: int, datos: TanqueEditar) -> Tanque:
    tanque = sesion.get(Tanque, tanque_id)
    if tanque is None:
        raise _no_encontrado("tanque")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(tanque, campo, valor)
    _guardar(sesion, "TANQUE_DUPLICADO", "Ya existe un tanque con ese nombre.")
    return tanque


def _validar_padre(sesion: Session, padre_id: int) -> None:
    padre = sesion.get(Nodo, padre_id)
    if padre is None:
        raise _no_encontrado("nodo")
    if padre.padre_id is not None:
        raise ErrorDeNegocio(
            status.HTTP_400_BAD_REQUEST,
            "PADRE_INVALIDO",
            "El nodo padre debe ser un autónomo, no un satélite.",
        )


def crear_nodo(sesion: Session, datos: NodoCrear) -> tuple[Nodo, str | None]:
    """Da de alta un nodo. El token en claro solo existe en lo que devuelve esta función."""
    if sesion.get(Tanque, datos.tanque_id) is None:
        raise _no_encontrado("tanque")
    if datos.padre_id is not None:
        _validar_padre(sesion, datos.padre_id)

    token = None if datos.padre_id is not None else secrets.token_urlsafe(_BYTES_TOKEN)
    nodo = Nodo(
        mac=datos.mac,
        nombre=datos.nombre,
        tanque_id=datos.tanque_id,
        padre_id=datos.padre_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest() if token else None,
    )
    sesion.add(nodo)
    _guardar(sesion, "NODO_DUPLICADO", "Esa MAC ya está registrada o el tanque ya tiene un nodo.")
    return nodo, token


def editar_nodo(sesion: Session, nodo_id: int, datos: NodoEditar) -> Nodo:
    nodo = sesion.get(Nodo, nodo_id)
    if nodo is None:
        raise _no_encontrado("nodo")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(nodo, campo, valor)
    sesion.commit()
    return nodo


def estado_de_tanques(sesion: Session, ahora: datetime) -> list[TanqueEstado]:
    filas = repo.tanques_con_nodo(sesion)
    nodo_ids = [nodo.id for _, nodo in filas if nodo is not None]
    modulos = repo.modulos_por_nodo(sesion, nodo_ids) if nodo_ids else {}
    lecturas: dict[int, list[LecturaActual]] = {}
    for fila in repo.ultimas_lecturas(sesion, nodo_ids) if nodo_ids else []:
        lecturas.setdefault(fila.nodo_id, []).append(
            LecturaActual(
                variable=fila.codigo,
                nombre=fila.nombre,
                unidad=fila.unidad,
                tipo=fila.tipo.value,
                valor=float(fila.valor),
                medido_en=fila.medido_en,
            )
        )

    resultado = []
    for tanque, nodo in filas:
        base = TanqueSalida.model_validate(tanque).model_dump()
        if nodo is None:
            resultado.append(TanqueEstado(**base, estado="sin_nodo", nodo=None, lecturas=[]))
            continue
        sin_conexion = esta_sin_conexion(nodo.ultimo_contacto, ahora)
        resultado.append(
            TanqueEstado(
                **base,
                estado="sin_conexion" if sin_conexion else "en_linea",
                nodo=NodoResumen(
                    id=nodo.id,
                    nombre=nodo.nombre,
                    mac=nodo.mac,
                    es_satelite=nodo.padre_id is not None,
                    activo=nodo.activo,
                    firmware=nodo.firmware,
                    ultimo_contacto=nodo.ultimo_contacto,
                    modulos=modulos.get(nodo.id, []),
                ),
                lecturas=lecturas.get(nodo.id, []),
            )
        )
    return resultado
