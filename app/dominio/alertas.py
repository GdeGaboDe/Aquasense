"""Evaluación de umbrales con histéresis (CLAUDE.md, 7.2)."""

from decimal import Decimal
from enum import StrEnum

FUERA_DE_RANGO = "FUERA_DE_RANGO"
COMANDO_FALLIDO = "COMANDO_FALLIDO"
# Variables booleanas que abren una alerta cuando valen 1.
ALERTA_POR_VARIABLE_BOOLEANA = {
    "flotador_bajo": "NIVEL_BAJO",
    "tolva_vacia": "TOLVA_VACIA",
}


class Accion(StrEnum):
    ABRIR = "abrir"
    RESOLVER = "resolver"
    NINGUNA = "ninguna"


def evaluar_numerica(
    valor: Decimal,
    minimo: Decimal | None,
    maximo: Decimal | None,
    histeresis: Decimal,
    activa: bool,
) -> Accion:
    """Abre al salir de [minimo, maximo]; resuelve solo al volver a [minimo + h, maximo - h].

    La banda evita que una lectura que oscila justo en el límite abra y cierre alertas sin parar.
    """
    if not activa:
        fuera = (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo)
        return Accion.ABRIR if fuera else Accion.NINGUNA

    dentro_de_la_banda = (minimo is None or valor >= minimo + histeresis) and (
        maximo is None or valor <= maximo - histeresis
    )
    return Accion.RESOLVER if dentro_de_la_banda else Accion.NINGUNA


def evaluar_booleana(valor: Decimal, activa: bool) -> Accion:
    if valor == 1 and not activa:
        return Accion.ABRIR
    if valor == 0 and activa:
        return Accion.RESOLVER
    return Accion.NINGUNA


def motivo_umbral_invalido(
    minimo: Decimal | None,
    maximo: Decimal | None,
    histeresis: Decimal,
    min_fisico: Decimal | None,
    max_fisico: Decimal | None,
) -> str | None:
    """Revisa un umbral antes de guardarlo; devuelve el motivo del rechazo o None."""
    if histeresis < 0:
        return "HISTERESIS_NEGATIVA"
    for limite in (minimo, maximo):
        if limite is None:
            continue
        if (min_fisico is not None and limite < min_fisico) or (
            max_fisico is not None and limite > max_fisico
        ):
            return "FUERA_DE_RANGO_FISICO"
    if minimo is not None and maximo is not None:
        if minimo >= maximo:
            return "MINIMO_NO_MENOR_QUE_MAXIMO"
        # Con una banda que cubre todo el rango, la alerta no podría resolverse nunca.
        if 2 * histeresis >= maximo - minimo:
            return "HISTERESIS_DEMASIADO_GRANDE"
    return None
