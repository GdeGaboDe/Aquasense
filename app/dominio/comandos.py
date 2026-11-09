"""Comandos remotos: argumentos, estados y transiciones (CLAUDE.md, 7.3)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

PENDIENTE = "pendiente"
ENTREGADO = "entregado"
CONFIRMADO = "confirmado"
FALLIDO = "fallido"
EXPIRADO = "expirado"
SIN_CONFIRMAR = "sin_confirmar"  # Solo para mostrar; en la base sigue como entregado

DISPENSAR = "DISPENSAR"

EXPIRACION_PENDIENTE = timedelta(seconds=120)
ESPERA_CONFIRMACION = timedelta(seconds=60)

_TRANSICIONES = {
    PENDIENTE: {ENTREGADO, EXPIRADO},
    ENTREGADO: {CONFIRMADO, FALLIDO},
}


@dataclass(frozen=True)
class ReglaArgumento:
    minimo: int
    maximo: int
    modulo: str


REGLAS = {
    DISPENSAR: ReglaArgumento(1, 5, "servo"),  # cargas
    "SILENCIAR_ALARMA": ReglaArgumento(1, 60, "alarma"),  # minutos
    "AIREADOR": ReglaArgumento(0, 1, "aireador"),  # 0 apagar, 1 encender
}


class TransicionInvalida(ValueError):
    def __init__(self, desde: str, hacia: str) -> None:
        super().__init__(f"Un comando {desde} no puede pasar a {hacia}.")
        self.desde = desde
        self.hacia = hacia


def puede_pasar(desde: str, hacia: str) -> bool:
    return hacia in _TRANSICIONES.get(desde, set())


def motivo_comando_invalido(tipo: str, argumento: int | None, modulos: set[str]) -> str | None:
    regla = REGLAS.get(tipo)
    if regla is None:
        return "TIPO_DESCONOCIDO"
    if regla.modulo not in modulos:
        return "MODULO_NO_DISPONIBLE"
    if argumento is None or not regla.minimo <= argumento <= regla.maximo:
        return "ARGUMENTO_INVALIDO"
    return None


def estado_a_aplicar(estado: str, resultado: str) -> str | None:
    """Estado que deja un ACK; None si no cambia nada porque ya se había recibido el mismo.

    Raises:
        TransicionInvalida: el ACK contradice el estado actual (otro resultado o sin entregar).
    """
    if estado == resultado:
        return None
    if not puede_pasar(estado, resultado):
        raise TransicionInvalida(estado, resultado)
    return resultado


def estado_mostrado(estado: str, entregado_en: datetime | None, ahora: datetime) -> str:
    """Un comando entregado sin ACK en 60 s se muestra "sin confirmar"; nunca se reenvía."""
    if (
        estado == ENTREGADO
        and entregado_en is not None
        and ahora - entregado_en > ESPERA_CONFIRMACION
    ):
        return SIN_CONFIRMAR
    return estado


def bloquea_otro_dispensar(estado: str, entregado_en: datetime | None, ahora: datetime) -> bool:
    """Un DISPENSAR en curso impide crear otro: mejor no dispensar que dar doble ración.

    Uno entregado sin ACK deja de bloquear al pasar a "sin confirmar"; si no, un ACK perdido
    impediría alimentar desde la web para siempre.
    """
    if estado == PENDIENTE:
        return True
    return estado_mostrado(estado, entregado_en, ahora) == ENTREGADO
