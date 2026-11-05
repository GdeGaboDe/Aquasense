"""Validación del valor de una lectura contra el catálogo de variables."""

from decimal import Decimal

MOTIVO_FUERA_DE_RANGO = "FUERA_DE_RANGO_FISICO"
MOTIVO_NO_BOOLEANO = "VALOR_NO_BOOLEANO"
_TIPO_BOOLEANO = "booleano"


def motivo_de_rechazo(
    valor: Decimal,
    tipo: str,
    minimo: Decimal | None,
    maximo: Decimal | None,
) -> str | None:
    """Devuelve el motivo por el que el valor no es aceptable, o None si lo es."""
    if tipo == _TIPO_BOOLEANO and valor not in (Decimal(0), Decimal(1)):
        return MOTIVO_NO_BOOLEANO
    if minimo is not None and valor < minimo:
        return MOTIVO_FUERA_DE_RANGO
    if maximo is not None and valor > maximo:
        return MOTIVO_FUERA_DE_RANGO
    return None
