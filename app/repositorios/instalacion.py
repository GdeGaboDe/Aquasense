"""Consultas de usuarios, tanques y nodos."""

from collections.abc import Iterable, Sequence

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from app.modelos import Lectura, Nodo, NodoModulo, OrigenHora, Sensor, Tanque, Usuario, Variable

_MAX_TANQUES = 200


def buscar_usuario(sesion: Session, nombre: str) -> Usuario | None:
    return sesion.scalar(select(Usuario).where(Usuario.usuario == nombre))


def buscar_tanque_por_nombre(sesion: Session, nombre: str) -> Tanque | None:
    return sesion.scalar(select(Tanque).where(Tanque.nombre == nombre))


def buscar_nodo_por_mac(sesion: Session, mac: str) -> Nodo | None:
    return sesion.scalar(select(Nodo).where(Nodo.mac == mac))


def buscar_nodo_de_tanque(sesion: Session, tanque_id: int) -> Nodo | None:
    return sesion.scalar(select(Nodo).where(Nodo.tanque_id == tanque_id))


def tanques_con_nodo(sesion: Session) -> Sequence[Row[tuple[Tanque, Nodo | None]]]:
    consulta = (
        select(Tanque, Nodo)
        .outerjoin(Nodo, Nodo.tanque_id == Tanque.id)
        .order_by(Tanque.nombre)
        .limit(_MAX_TANQUES)
    )
    return sesion.execute(consulta).all()


def modulos_por_nodo(sesion: Session, nodo_ids: Iterable[int]) -> dict[int, list[str]]:
    consulta = (
        select(NodoModulo.nodo_id, NodoModulo.modulo)
        .where(NodoModulo.nodo_id.in_(set(nodo_ids)))
        .order_by(NodoModulo.modulo)
    )
    modulos: dict[int, list[str]] = {}
    for fila in sesion.execute(consulta):
        modulos.setdefault(fila.nodo_id, []).append(fila.modulo)
    return modulos


def ultimas_lecturas(sesion: Session, nodo_ids: Iterable[int]) -> Sequence[Row]:
    """Última lectura con hora confiable de cada sensor de los nodos indicados."""
    ultima = (
        select(Lectura.sensor_id, func.max(Lectura.medido_en).label("medido_en"))
        .join(Sensor, Sensor.id == Lectura.sensor_id)
        .where(
            Sensor.nodo_id.in_(set(nodo_ids)),
            Lectura.origen_hora != OrigenHora.DESCONOCIDA,
        )
        .group_by(Lectura.sensor_id)
        .subquery()
    )
    consulta = (
        select(
            Sensor.nodo_id,
            Variable.codigo,
            Variable.nombre,
            Variable.unidad,
            Variable.tipo,
            Lectura.valor,
            Lectura.medido_en,
        )
        .join(
            ultima,
            (ultima.c.sensor_id == Lectura.sensor_id) & (ultima.c.medido_en == Lectura.medido_en),
        )
        .join(Sensor, Sensor.id == Lectura.sensor_id)
        .join(Variable, Variable.id == Sensor.variable_id)
        .order_by(Variable.id)
    )
    return sesion.execute(consulta).all()
