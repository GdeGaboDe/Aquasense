"""Consultas que usa la ingesta de telemetría."""

from collections.abc import Iterable, Sequence
from datetime import datetime
from itertools import batched

from sqlalchemy import delete, or_, select, tuple_, update
from sqlalchemy.orm import Session

from app.modelos import Comando, Dosis, Lectura, Nodo, NodoModulo, Sensor, Variable

_TAMANO_BLOQUE = 500


def buscar_autonomo_por_token(sesion: Session, token_hash: str) -> Nodo | None:
    return sesion.scalar(select(Nodo).where(Nodo.token_hash == token_hash))


def nodos_de_autonomo(sesion: Session, autonomo_id: int) -> Sequence[Nodo]:
    consulta = select(Nodo).where(or_(Nodo.id == autonomo_id, Nodo.padre_id == autonomo_id))
    return sesion.scalars(consulta).all()


def macs_registradas(sesion: Session, macs: Iterable[str]) -> set[str]:
    return set(sesion.scalars(select(Nodo.mac).where(Nodo.mac.in_(set(macs)))))


def todas_las_variables(sesion: Session) -> Sequence[Variable]:
    return sesion.scalars(select(Variable)).all()


def sensores_de_nodos(sesion: Session, nodo_ids: Iterable[int]) -> Sequence[Sensor]:
    return sesion.scalars(select(Sensor).where(Sensor.nodo_id.in_(set(nodo_ids)))).all()


def modulos_de_nodo(sesion: Session, nodo_id: int) -> set[str]:
    return set(sesion.scalars(select(NodoModulo.modulo).where(NodoModulo.nodo_id == nodo_id)))


def quitar_modulos(sesion: Session, nodo_id: int, modulos: Iterable[str]) -> None:
    sesion.execute(
        delete(NodoModulo).where(NodoModulo.nodo_id == nodo_id, NodoModulo.modulo.in_(set(modulos)))
    )


def marcar_sensores_vistos(
    sesion: Session, nodo_id: int, variable_ids: Iterable[int], momento: datetime
) -> None:
    sesion.execute(
        update(Sensor)
        .where(Sensor.nodo_id == nodo_id, Sensor.variable_id.in_(set(variable_ids)))
        .values(ultimo_visto=momento)
    )


def lecturas_existentes(
    sesion: Session, llaves: Iterable[tuple[int, datetime]]
) -> set[tuple[int, datetime]]:
    existentes: set[tuple[int, datetime]] = set()
    for bloque in batched(llaves, _TAMANO_BLOQUE):
        consulta = select(Lectura.sensor_id, Lectura.medido_en).where(
            tuple_(Lectura.sensor_id, Lectura.medido_en).in_(bloque)
        )
        existentes.update((fila.sensor_id, fila.medido_en) for fila in sesion.execute(consulta))
    return existentes


def dosis_existentes(
    sesion: Session, llaves: Iterable[tuple[int, datetime]]
) -> set[tuple[int, datetime]]:
    existentes: set[tuple[int, datetime]] = set()
    for bloque in batched(llaves, _TAMANO_BLOQUE):
        consulta = select(Dosis.nodo_id, Dosis.dosificada_en).where(
            tuple_(Dosis.nodo_id, Dosis.dosificada_en).in_(bloque)
        )
        existentes.update((fila.nodo_id, fila.dosificada_en) for fila in sesion.execute(consulta))
    return existentes


def duenos_de_comandos(sesion: Session, comando_ids: Iterable[int]) -> dict[int, int]:
    consulta = select(Comando.id, Comando.nodo_id).where(Comando.id.in_(set(comando_ids)))
    return {fila.id: fila.nodo_id for fila in sesion.execute(consulta)}


def comandos_con_dosis(sesion: Session, comando_ids: Iterable[int]) -> set[int]:
    consulta = select(Dosis.comando_id).where(Dosis.comando_id.in_(set(comando_ids)))
    return {comando_id for comando_id in sesion.scalars(consulta) if comando_id is not None}
