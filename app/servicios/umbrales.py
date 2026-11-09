"""Umbrales de cada tanque."""

from fastapi import status
from sqlalchemy.orm import Session

from app.dominio.alertas import motivo_umbral_invalido
from app.esquemas.control import UmbralesEditar, UmbralSalida
from app.modelos import Tanque, TipoVariable, Umbral, Variable
from app.repositorios import control as repo
from app.repositorios.instalacion import buscar_nodo_de_tanque
from app.servicios.errores import ErrorDeNegocio


def _flotante(valor) -> float | None:
    return float(valor) if valor is not None else None


def _obtener_tanque(sesion: Session, tanque_id: int) -> Tanque:
    tanque = sesion.get(Tanque, tanque_id)
    if tanque is None:
        raise ErrorDeNegocio(
            status.HTTP_404_NOT_FOUND, "TANQUE_NO_ENCONTRADO", "No existe ese tanque."
        )
    return tanque


def obtener(sesion: Session, tanque_id: int) -> list[UmbralSalida]:
    """Variables numéricas que reporta el nodo del tanque, más las que ya tengan umbral."""
    tanque = _obtener_tanque(sesion, tanque_id)
    filas = repo.umbrales_de_tanque(sesion, tanque.id)
    guardados = {variable.id: umbral for umbral, variable in filas}
    variables: dict[int, Variable] = {variable.id: variable for _, variable in filas}
    nodo = buscar_nodo_de_tanque(sesion, tanque.id)
    if nodo is not None:
        variables |= {v.id: v for v in repo.variables_reportadas(sesion, nodo.id)}

    resultado = []
    for variable_id in sorted(variables):
        variable = variables[variable_id]
        if variable.tipo != TipoVariable.NUMERO:
            continue
        umbral = guardados.get(variable_id)
        resultado.append(
            UmbralSalida(
                variable=variable.codigo,
                nombre=variable.nombre,
                unidad=variable.unidad,
                min_fisico=_flotante(variable.min_fisico),
                max_fisico=_flotante(variable.max_fisico),
                minimo=_flotante(umbral.minimo) if umbral else None,
                maximo=_flotante(umbral.maximo) if umbral else None,
                histeresis=float(umbral.histeresis) if umbral else 0.0,
            )
        )
    return resultado


def actualizar(sesion: Session, tanque_id: int, datos: UmbralesEditar) -> list[UmbralSalida]:
    """Guarda los umbrales enviados. Mínimo y máximo vacíos eliminan el umbral de esa variable."""
    tanque = _obtener_tanque(sesion, tanque_id)
    variables = repo.variables_por_codigo(sesion, [u.variable for u in datos.umbrales])
    actuales = repo.umbrales_de_tanques(sesion, [tanque.id])

    problemas = []
    for umbral in datos.umbrales:
        variable = variables.get(umbral.variable)
        if variable is None or variable.tipo != TipoVariable.NUMERO:
            problemas.append({"variable": umbral.variable, "motivo": "VARIABLE_NO_NUMERICA"})
            continue
        motivo = motivo_umbral_invalido(
            umbral.minimo,
            umbral.maximo,
            umbral.histeresis,
            variable.min_fisico,
            variable.max_fisico,
        )
        if motivo:
            problemas.append({"variable": umbral.variable, "motivo": motivo})
    if problemas:
        raise ErrorDeNegocio(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "UMBRALES_INVALIDOS",
            "Algunos umbrales no son válidos; no se guardó ningún cambio.",
            problemas,
        )

    for umbral in datos.umbrales:
        variable = variables[umbral.variable]
        existente = actuales.get((tanque.id, variable.id))
        if umbral.minimo is None and umbral.maximo is None:
            if existente is not None:
                sesion.delete(existente)
            continue
        if existente is None:
            existente = Umbral(tanque_id=tanque.id, variable_id=variable.id)
            sesion.add(existente)
        existente.minimo = umbral.minimo
        existente.maximo = umbral.maximo
        existente.histeresis = umbral.histeresis
    sesion.commit()
    return obtener(sesion, tanque.id)
