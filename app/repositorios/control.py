"""Consultas de alertas, umbrales, comandos, parámetros y dosis."""

from collections.abc import Iterable, Sequence
from datetime import datetime

from sqlalchemy import Row, Select, func, or_, select
from sqlalchemy.orm import Session

from app.modelos import (
    Alerta,
    Comando,
    Dosis,
    EstadoComando,
    Lectura,
    OrigenHora,
    Parametro,
    Sensor,
    Tanque,
    TipoAlerta,
    TipoComando,
    Umbral,
    ValorParametro,
    Variable,
)


def contar(sesion: Session, consulta: Select) -> int:
    return sesion.scalar(select(func.count()).select_from(consulta.order_by(None).subquery())) or 0


# --- Alertas y umbrales ---


def tipos_de_alerta(sesion: Session) -> dict[str, int]:
    return {
        fila.codigo: fila.id for fila in sesion.execute(select(TipoAlerta.codigo, TipoAlerta.id))
    }


def alertas_activas(sesion: Session, tanque_ids: Iterable[int]) -> Sequence[Alerta]:
    consulta = select(Alerta).where(
        Alerta.tanque_id.in_(set(tanque_ids)), Alerta.resuelta_en.is_(None)
    )
    return sesion.scalars(consulta).all()


def umbrales_de_tanques(
    sesion: Session, tanque_ids: Iterable[int]
) -> dict[tuple[int, int], Umbral]:
    consulta = select(Umbral).where(Umbral.tanque_id.in_(set(tanque_ids)))
    return {(u.tanque_id, u.variable_id): u for u in sesion.scalars(consulta)}


def ultima_medicion_confiable(sesion: Session, sensor_ids: Iterable[int]) -> dict[int, datetime]:
    consulta = (
        select(Lectura.sensor_id, func.max(Lectura.medido_en))
        .where(
            Lectura.sensor_id.in_(set(sensor_ids)),
            Lectura.origen_hora != OrigenHora.DESCONOCIDA,
        )
        .group_by(Lectura.sensor_id)
    )
    return {sensor_id: momento for sensor_id, momento in sesion.execute(consulta)}


def _consulta_alertas() -> Select:
    return (
        select(Alerta, TipoAlerta, Variable, Tanque.nombre.label("tanque_nombre"))
        .join(TipoAlerta, TipoAlerta.id == Alerta.tipo_alerta_id)
        .join(Tanque, Tanque.id == Alerta.tanque_id)
        .outerjoin(Variable, Variable.id == Alerta.variable_id)
    )


def listar_alertas(
    sesion: Session, activa: bool | None, tanque_id: int | None, desde: int, limite: int
) -> tuple[Sequence[Row], int]:
    consulta = _consulta_alertas()
    if activa is not None:
        consulta = consulta.where(
            Alerta.resuelta_en.is_(None) if activa else Alerta.resuelta_en.is_not(None)
        )
    if tanque_id is not None:
        consulta = consulta.where(Alerta.tanque_id == tanque_id)
    total = contar(sesion, consulta)
    filas = sesion.execute(
        consulta.order_by(Alerta.iniciada_en.desc(), Alerta.id.desc()).offset(desde).limit(limite)
    ).all()
    return filas, total


def alertas_activas_detalladas(sesion: Session, tanque_ids: Iterable[int]) -> Sequence[Row]:
    consulta = _consulta_alertas().where(
        Alerta.tanque_id.in_(set(tanque_ids)), Alerta.resuelta_en.is_(None)
    )
    return sesion.execute(consulta.order_by(Alerta.iniciada_en)).all()


def variables_reportadas(sesion: Session, nodo_id: int) -> Sequence[Variable]:
    consulta = (
        select(Variable)
        .join(Sensor, Sensor.variable_id == Variable.id)
        .where(Sensor.nodo_id == nodo_id)
        .order_by(Variable.id)
    )
    return sesion.scalars(consulta).all()


def umbrales_de_tanque(sesion: Session, tanque_id: int) -> Sequence[Row[tuple[Umbral, Variable]]]:
    consulta = (
        select(Umbral, Variable)
        .join(Variable, Variable.id == Umbral.variable_id)
        .where(Umbral.tanque_id == tanque_id)
    )
    return sesion.execute(consulta).all()


def variables_por_codigo(sesion: Session, codigos: Iterable[str]) -> dict[str, Variable]:
    consulta = select(Variable).where(Variable.codigo.in_(set(codigos)))
    return {v.codigo: v for v in sesion.scalars(consulta)}


# --- Comandos ---


def pendientes_vencidos(
    sesion: Session, ahora: datetime, nodo_ids: Iterable[int] | None = None
) -> Sequence[Comando]:
    consulta = select(Comando).where(
        Comando.estado == EstadoComando.PENDIENTE, Comando.expira_en <= ahora
    )
    if nodo_ids is not None:
        consulta = consulta.where(Comando.nodo_id.in_(set(nodo_ids)))
    return sesion.scalars(consulta).all()


def pendientes_de_nodos(sesion: Session, nodo_ids: Iterable[int]) -> Sequence[Comando]:
    consulta = (
        select(Comando)
        .where(Comando.nodo_id.in_(set(nodo_ids)), Comando.estado == EstadoComando.PENDIENTE)
        .order_by(Comando.id)
    )
    return sesion.scalars(consulta).all()


def dispensar_en_curso(sesion: Session, nodo_id: int) -> Sequence[Comando]:
    consulta = select(Comando).where(
        Comando.nodo_id == nodo_id,
        Comando.tipo == TipoComando.DISPENSAR,
        or_(
            Comando.estado == EstadoComando.PENDIENTE,
            Comando.estado == EstadoComando.ENTREGADO,
        ),
    )
    return sesion.scalars(consulta).all()


def listar_comandos(
    sesion: Session, nodo_id: int | None, desde: int, limite: int
) -> tuple[Sequence[Comando], int]:
    consulta = select(Comando)
    if nodo_id is not None:
        consulta = consulta.where(Comando.nodo_id == nodo_id)
    total = contar(sesion, consulta)
    filas = sesion.scalars(consulta.order_by(Comando.id.desc()).offset(desde).limit(limite)).all()
    return filas, total


# --- Parámetros ---


def catalogo_de_parametros(sesion: Session) -> Sequence[Parametro]:
    return sesion.scalars(select(Parametro).order_by(Parametro.id)).all()


def valores_de_nodos(
    sesion: Session, nodo_ids: Iterable[int]
) -> dict[int, dict[int, ValorParametro]]:
    consulta = select(ValorParametro).where(ValorParametro.nodo_id.in_(set(nodo_ids)))
    valores: dict[int, dict[int, ValorParametro]] = {}
    for valor in sesion.scalars(consulta):
        valores.setdefault(valor.nodo_id, {})[valor.parametro_id] = valor
    return valores


# --- Dosis ---


def listar_dosis(
    sesion: Session, nodo_id: int, desde: int, limite: int
) -> tuple[Sequence[Dosis], int]:
    consulta = select(Dosis).where(Dosis.nodo_id == nodo_id)
    total = contar(sesion, consulta)
    filas = sesion.scalars(
        consulta.order_by(Dosis.dosificada_en.desc()).offset(desde).limit(limite)
    ).all()
    return filas, total
