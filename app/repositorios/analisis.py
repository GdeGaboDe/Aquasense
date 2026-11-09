"""Consultas de series, cambios de agua y predicciones."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import CambioAgua, Lectura, Nodo, OrigenHora, Prediccion, Sensor, Umbral, Variable
from app.repositorios.control import contar

_ORIGENES_CONFIABLES = (OrigenHora.SERVIDOR, OrigenHora.NTP)


def sensor_de_tanque(sesion: Session, tanque_id: int, codigo_variable: str) -> int | None:
    consulta = (
        select(Sensor.id)
        .join(Nodo, Nodo.id == Sensor.nodo_id)
        .join(Variable, Variable.id == Sensor.variable_id)
        .where(Nodo.tanque_id == tanque_id, Variable.codigo == codigo_variable)
    )
    return sesion.scalar(consulta)


def lecturas_de_sensor(
    sesion: Session,
    sensor_id: int,
    desde: datetime,
    hasta: datetime,
    incluir_desconocidas: bool = False,
) -> list[tuple[datetime, float]]:
    consulta = select(Lectura.medido_en, Lectura.valor).where(
        Lectura.sensor_id == sensor_id, Lectura.medido_en >= desde, Lectura.medido_en < hasta
    )
    if not incluir_desconocidas:
        consulta = consulta.where(Lectura.origen_hora.in_(_ORIGENES_CONFIABLES))
    filas = sesion.execute(consulta.order_by(Lectura.medido_en)).yield_per(5000)
    return [(momento, float(valor)) for momento, valor in filas]


def cambios_de_tanque(sesion: Session, tanque_id: int) -> Sequence[CambioAgua]:
    consulta = (
        select(CambioAgua)
        .where(CambioAgua.tanque_id == tanque_id)
        .order_by(CambioAgua.realizado_en, CambioAgua.id)
    )
    return sesion.scalars(consulta).all()


def listar_cambios(
    sesion: Session, tanque_id: int, desde: int, limite: int
) -> tuple[Sequence[CambioAgua], int]:
    consulta = select(CambioAgua).where(CambioAgua.tanque_id == tanque_id)
    total = contar(sesion, consulta)
    filas = sesion.scalars(
        consulta.order_by(CambioAgua.realizado_en.desc()).offset(desde).limit(limite)
    ).all()
    return filas, total


def limite_tds(sesion: Session, tanque_id: int) -> float | None:
    consulta = (
        select(Umbral.maximo)
        .join(Variable, Variable.id == Umbral.variable_id)
        .where(Umbral.tanque_id == tanque_id, Variable.codigo == "tds_ppm")
    )
    maximo = sesion.scalar(consulta)
    return float(maximo) if maximo is not None else None


def ultima_prediccion(sesion: Session, cambio_agua_id: int) -> Prediccion | None:
    consulta = (
        select(Prediccion)
        .where(Prediccion.cambio_agua_id == cambio_agua_id)
        .order_by(Prediccion.generada_en.desc())
        .limit(1)
    )
    return sesion.scalar(consulta)
