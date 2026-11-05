"""Guarda un lote de telemetría: nodos, lecturas y eventos (CLAUDE.md, 6.1 y 7.1)."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dominio.lecturas import motivo_de_rechazo
from app.dominio.modulos import modulos_conocidos, variables_de_modulos
from app.dominio.tiempo import asignar_hora
from app.esquemas.dispositivo import (
    EventoDosis,
    LecturaReportada,
    LoteTelemetria,
    NodoReportado,
    Rechazo,
    RespuestaTelemetria,
)
from app.modelos import Dosis, Lectura, Nodo, NodoModulo, Sensor, Variable
from app.repositorios import ingesta as repo
from app.servicios.errores import ErrorDeNegocio

_MAC_NO_REGISTRADA = "MAC_NO_REGISTRADA"
_NODO_AJENO = "NODO_AJENO"
_NODO_INACTIVO = "NODO_INACTIVO"
_VARIABLE_DESCONOCIDA = "VARIABLE_DESCONOCIDA"
_VARIABLE_NO_ANUNCIADA = "VARIABLE_NO_ANUNCIADA"
_COMANDO_INVALIDO = "COMANDO_INVALIDO"


@dataclass
class _Conteo:
    aceptadas: int = 0
    duplicadas: int = 0
    rechazadas: list[Rechazo] = field(default_factory=list)


@dataclass(frozen=True)
class _Contexto:
    nodos_por_mac: dict[str, Nodo]
    macs_ajenas: set[str]
    boot_actual: int | None
    recibido_en: datetime


def _motivo_por_nodo(mac: str, contexto: _Contexto) -> str | None:
    nodo = contexto.nodos_por_mac.get(mac)
    if nodo is None:
        return _NODO_AJENO if mac in contexto.macs_ajenas else _MAC_NO_REGISTRADA
    return None if nodo.activo else _NODO_INACTIVO


def _sincronizar_modulos(
    sesion: Session, nodo: Nodo, anunciados: set[str], ahora: datetime
) -> None:
    actuales = repo.modulos_de_nodo(sesion, nodo.id)
    if retirados := actuales - anunciados:
        repo.quitar_modulos(sesion, nodo.id, retirados)
    sesion.add_all(
        NodoModulo(nodo_id=nodo.id, modulo=modulo, detectado_en=ahora)
        for modulo in anunciados - actuales
    )


def _sincronizar_sensores(
    sesion: Session,
    nodo: Nodo,
    anunciados: set[str],
    variables: dict[str, Variable],
    sensores: dict[tuple[int, int], int],
    ahora: datetime,
) -> None:
    """Crea los sensores nuevos (autodescubrimiento) y marca como vistos los anunciados."""
    variable_ids = {
        variables[codigo].id for codigo in variables_de_modulos(anunciados) if codigo in variables
    }
    for variable_id in variable_ids:
        if (nodo.id, variable_id) not in sensores:
            sensor = Sensor(
                nodo_id=nodo.id, variable_id=variable_id, detectado_en=ahora, ultimo_visto=ahora
            )
            sesion.add(sensor)
            sesion.flush()
            sensores[(nodo.id, variable_id)] = sensor.id
    if variable_ids:
        repo.marcar_sensores_vistos(sesion, nodo.id, variable_ids, ahora)


def _actualizar_nodo(
    sesion: Session,
    nodo: Nodo,
    reportado: NodoReportado,
    variables: dict[str, Variable],
    sensores: dict[tuple[int, int], int],
    ahora: datetime,
) -> None:
    nodo.firmware = reportado.firmware
    nodo.boot_actual = reportado.boot
    nodo.config_version_aplicada = reportado.config_version_aplicada
    nodo.ultimo_contacto = ahora
    anunciados = modulos_conocidos(reportado.modulos)
    _sincronizar_modulos(sesion, nodo, anunciados, ahora)
    _sincronizar_sensores(sesion, nodo, anunciados, variables, sensores, ahora)


def _procesar_lecturas(
    sesion: Session,
    lecturas: list[LecturaReportada],
    contexto: _Contexto,
    variables: dict[str, Variable],
    sensores: dict[tuple[int, int], int],
    conteo: _Conteo,
) -> None:
    filas: dict[tuple[int, datetime], Lectura] = {}
    for indice, lectura in enumerate(lecturas):
        motivo = _motivo_por_nodo(lectura.mac, contexto)
        variable = variables.get(lectura.variable)
        sensor_id = None
        valor = Decimal(str(round(lectura.valor, 3)))
        if motivo is None and variable is None:
            motivo = _VARIABLE_DESCONOCIDA
        if motivo is None and variable is not None:
            nodo = contexto.nodos_por_mac[lectura.mac]
            sensor_id = sensores.get((nodo.id, variable.id))
            motivo = motivo_de_rechazo(
                valor, variable.tipo.value, variable.min_fisico, variable.max_fisico
            )
            if motivo is None and sensor_id is None:
                motivo = _VARIABLE_NO_ANUNCIADA
        if motivo is not None or sensor_id is None:
            conteo.rechazadas.append(
                Rechazo(lista="lecturas", indice=indice, motivo=motivo or _VARIABLE_NO_ANUNCIADA)
            )
            continue

        hora = asignar_hora(
            contexto.recibido_en,
            contexto.boot_actual,
            lectura.boot,
            lectura.edad_ms,
            lectura.epoch_ms,
        )
        llave = (sensor_id, hora.medido_en)
        if llave in filas:
            conteo.duplicadas += 1
            continue
        filas[llave] = Lectura(
            sensor_id=sensor_id,
            medido_en=hora.medido_en,
            valor=valor,
            recibido_en=contexto.recibido_en,
            origen_hora=hora.origen,
        )

    existentes = repo.lecturas_existentes(sesion, filas)
    nuevas = [fila for llave, fila in filas.items() if llave not in existentes]
    sesion.add_all(nuevas)
    conteo.aceptadas += len(nuevas)
    conteo.duplicadas += len(existentes)


def _procesar_eventos(
    sesion: Session,
    eventos: list[EventoDosis],
    contexto: _Contexto,
    conteo: _Conteo,
) -> None:
    ids_comando = {e.comando_id for e in eventos if e.comando_id is not None}
    duenos = repo.duenos_de_comandos(sesion, ids_comando) if ids_comando else {}
    # Un reenvío del mismo evento trae otra hora asignada, pero el mismo comando: no es otra dosis.
    ya_ligados = repo.comandos_con_dosis(sesion, ids_comando) if ids_comando else set()

    filas: dict[tuple[int, datetime], Dosis] = {}
    for indice, evento in enumerate(eventos):
        motivo = _motivo_por_nodo(evento.mac, contexto)
        if motivo is None:
            nodo_id = contexto.nodos_por_mac[evento.mac].id
            if evento.comando_id is not None and duenos.get(evento.comando_id) != nodo_id:
                motivo = _COMANDO_INVALIDO
        if motivo is not None:
            conteo.rechazadas.append(Rechazo(lista="eventos", indice=indice, motivo=motivo))
            continue
        if evento.comando_id in ya_ligados:
            conteo.duplicadas += 1
            continue

        hora = asignar_hora(
            contexto.recibido_en,
            contexto.boot_actual,
            evento.boot,
            evento.edad_ms,
            evento.epoch_ms,
        )
        llave = (nodo_id, hora.medido_en)
        if llave in filas:
            conteo.duplicadas += 1
            continue
        if evento.comando_id is not None:
            ya_ligados.add(evento.comando_id)
        filas[llave] = Dosis(
            nodo_id=nodo_id,
            cargas=evento.cargas,
            origen=evento.origen,
            dosificada_en=hora.medido_en,
            comando_id=evento.comando_id,
        )

    existentes = repo.dosis_existentes(sesion, filas)
    nuevas = [fila for llave, fila in filas.items() if llave not in existentes]
    sesion.add_all(nuevas)
    conteo.aceptadas += len(nuevas)
    conteo.duplicadas += len(existentes)


def ingerir_lote(
    sesion: Session, autonomo: Nodo, lote: LoteTelemetria, recibido_en: datetime
) -> RespuestaTelemetria:
    """Guarda el lote en una sola transacción y rechaza individualmente lo que no sea válido."""
    propios = {nodo.mac: nodo for nodo in repo.nodos_de_autonomo(sesion, autonomo.id)}
    macs_reportadas = {x.mac for x in lote.lecturas} | {x.mac for x in lote.eventos}
    macs_externas = macs_reportadas - propios.keys()
    macs_ajenas = repo.macs_registradas(sesion, macs_externas) if macs_externas else set()
    variables = {v.codigo: v for v in repo.todas_las_variables(sesion)}
    sensores = {
        (s.nodo_id, s.variable_id): s.id
        for s in repo.sensores_de_nodos(sesion, [n.id for n in propios.values()])
    }

    boot_actual = None
    for reportado in lote.nodos:
        nodo = propios.get(reportado.mac)
        if nodo is None or not nodo.activo:
            continue
        if nodo.id == autonomo.id:
            boot_actual = reportado.boot
        _actualizar_nodo(sesion, nodo, reportado, variables, sensores, recibido_en)
    autonomo.ultimo_contacto = recibido_en

    contexto = _Contexto(propios, macs_ajenas, boot_actual, recibido_en)
    conteo = _Conteo()
    _procesar_lecturas(sesion, lote.lecturas, contexto, variables, sensores, conteo)
    _procesar_eventos(sesion, lote.eventos, contexto, conteo)

    try:
        sesion.commit()
    except IntegrityError as error:
        # Dos envíos simultáneos del mismo dato: el nodo debe reintentar y saldrá como duplicado.
        sesion.rollback()
        raise ErrorDeNegocio(
            status.HTTP_409_CONFLICT,
            "LOTE_EN_CONFLICTO",
            "Otro envío guardó estos datos al mismo tiempo. Reintenta el lote.",
        ) from error

    return RespuestaTelemetria(
        aceptadas=conteo.aceptadas,
        duplicadas=conteo.duplicadas,
        rechazadas=conteo.rechazadas,
    )
