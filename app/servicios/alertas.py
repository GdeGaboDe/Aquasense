"""Apertura y cierre de alertas, y su consulta (CLAUDE.md, 7.2)."""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.orm import Session

from app.dominio.alertas import (
    ALERTA_POR_VARIABLE_BOOLEANA,
    COMANDO_FALLIDO,
    FUERA_DE_RANGO,
    Accion,
    evaluar_booleana,
    evaluar_numerica,
)
from app.esquemas.control import AlertaSalida, Pagina
from app.modelos import Alerta, Comando, Lectura, Nodo, OrigenHora, TipoVariable, Variable
from app.repositorios import control as repo

_Llave = tuple[int, int, int | None]  # tanque, tipo de alerta, variable


def _ultima_por_sensor(lecturas: Iterable[Lectura]) -> dict[int, Lectura]:
    ultimas: dict[int, Lectura] = {}
    for lectura in lecturas:
        actual = ultimas.get(lectura.sensor_id)
        if actual is None or lectura.medido_en > actual.medido_en:
            ultimas[lectura.sensor_id] = lectura
    return ultimas


def evaluar_lecturas(
    sesion: Session,
    lecturas: list[Lectura],
    contexto: dict[int, tuple[Nodo, Variable]],
) -> None:
    """Abre o resuelve alertas con la lectura más reciente de cada sensor del lote.

    Debe llamarse antes de agregar las lecturas a la sesión. Se ignoran las lecturas de hora
    desconocida y las atrasadas (reenvíos de LittleFS más viejos que lo ya guardado): evaluarlas
    reabriría o cerraría alertas con datos que ya no representan el estado actual.
    """
    confiables = [x for x in lecturas if x.origen_hora != OrigenHora.DESCONOCIDA]
    ultimas = _ultima_por_sensor(confiables)
    if not ultimas:
        return
    previas = repo.ultima_medicion_confiable(sesion, ultimas)
    vigentes = {
        sensor_id: lectura
        for sensor_id, lectura in ultimas.items()
        if sensor_id not in previas or lectura.medido_en > previas[sensor_id]
    }
    tanques = {contexto[s][0].tanque_id for s in vigentes}
    if not tanques:
        return

    tipos = repo.tipos_de_alerta(sesion)
    umbrales = repo.umbrales_de_tanques(sesion, tanques)
    activas: dict[_Llave, Alerta] = {
        (a.tanque_id, a.tipo_alerta_id, a.variable_id): a
        for a in repo.alertas_activas(sesion, tanques)
    }

    for sensor_id, lectura in vigentes.items():
        nodo, variable = contexto[sensor_id]
        tanque_id = nodo.tanque_id
        if variable.tipo == TipoVariable.BOOLEANO:
            codigo = ALERTA_POR_VARIABLE_BOOLEANA.get(variable.codigo)
            if codigo is None:
                continue
            llave = (tanque_id, tipos[codigo], variable.id)
            accion = evaluar_booleana(lectura.valor, llave in activas)
        else:
            umbral = umbrales.get((tanque_id, variable.id))
            if umbral is None:
                continue
            llave = (tanque_id, tipos[FUERA_DE_RANGO], variable.id)
            accion = evaluar_numerica(
                lectura.valor, umbral.minimo, umbral.maximo, umbral.histeresis, llave in activas
            )

        if accion == Accion.ABRIR:
            alerta = Alerta(
                tanque_id=tanque_id,
                nodo_id=nodo.id,
                tipo_alerta_id=llave[1],
                variable_id=variable.id,
                valor=lectura.valor,
                iniciada_en=lectura.medido_en,
            )
            sesion.add(alerta)
            activas[llave] = alerta
        elif accion == Accion.RESOLVER:
            alerta = activas.pop(llave)
            alerta.resuelta_en = max(lectura.medido_en, alerta.iniciada_en)


def abrir_por_comando(sesion: Session, comando: Comando, tanque_id: int, momento: datetime) -> None:
    """Un comando fallido o expirado abre COMANDO_FALLIDO, sin duplicar una ya activa."""
    tipo_id = repo.tipos_de_alerta(sesion)[COMANDO_FALLIDO]
    for activa in repo.alertas_activas(sesion, [tanque_id]):
        if activa.tipo_alerta_id == tipo_id:
            return
    sesion.add(
        Alerta(
            tanque_id=tanque_id,
            nodo_id=comando.nodo_id,
            tipo_alerta_id=tipo_id,
            iniciada_en=momento,
        )
    )
    sesion.flush()


def resolver_por_comando_exitoso(sesion: Session, tanque_id: int, momento: datetime) -> None:
    """La alerta de comando fallido se cierra cuando un comando posterior se confirma."""
    tipo_id = repo.tipos_de_alerta(sesion)[COMANDO_FALLIDO]
    for activa in repo.alertas_activas(sesion, [tanque_id]):
        if activa.tipo_alerta_id == tipo_id:
            activa.resuelta_en = max(momento, activa.iniciada_en)


def _a_salida(fila) -> AlertaSalida:
    alerta, tipo, variable = fila.Alerta, fila.TipoAlerta, fila.Variable
    return AlertaSalida(
        id=alerta.id,
        tanque_id=alerta.tanque_id,
        tanque=fila.tanque_nombre,
        tipo=tipo.codigo,
        descripcion=tipo.descripcion,
        severidad=tipo.severidad.value,
        variable=variable.codigo if variable else None,
        variable_nombre=variable.nombre if variable else None,
        unidad=variable.unidad if variable else None,
        valor=float(alerta.valor) if alerta.valor is not None else None,
        iniciada_en=alerta.iniciada_en,
        resuelta_en=alerta.resuelta_en,
        activa=alerta.resuelta_en is None,
    )


def listar(
    sesion: Session, activa: bool | None, tanque_id: int | None, pagina: int, tamano: int
) -> Pagina[AlertaSalida]:
    filas, total = repo.listar_alertas(sesion, activa, tanque_id, (pagina - 1) * tamano, tamano)
    return Pagina(
        elementos=[_a_salida(f) for f in filas], total=total, pagina=pagina, tamano=tamano
    )


def activas_por_tanque(sesion: Session, tanque_ids: list[int]) -> dict[int, list[AlertaSalida]]:
    resultado: dict[int, list[AlertaSalida]] = {}
    for fila in repo.alertas_activas_detalladas(sesion, tanque_ids) if tanque_ids else []:
        resultado.setdefault(fila.Alerta.tanque_id, []).append(_a_salida(fila))
    return resultado
