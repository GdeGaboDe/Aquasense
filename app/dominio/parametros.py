"""Validación de parámetros configurables (CLAUDE.md, 7.4)."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

ENTERO = "entero"
DECIMAL = "decimal"
OPCION = "opcion"

# (debe ser menor, debe ser mayor): solo se revisa si el nodo tiene ambos parámetros.
REGLAS_ENTRE_PARAMETROS = (
    ("UMBRAL_LUZ_OSCURIDAD", "UMBRAL_LUZ_MODERADA"),
    ("ANGULO_REPOSO_SERVO", "ANGULO_DISPENSA_SERVO"),
    ("TEMP_ENCENDER_CALENTADOR", "TEMP_APAGAR_CALENTADOR"),
)


@dataclass(frozen=True)
class DefinicionParametro:
    codigo: str
    tipo: str
    minimo: Decimal | None
    maximo: Decimal | None
    opciones: tuple[str, ...] | None
    valor_defecto: str
    modulo_requerido: str | None


@dataclass(frozen=True)
class Problema:
    parametro: str
    motivo: str


def aplica_al_nodo(definicion: DefinicionParametro, modulos: set[str]) -> bool:
    return definicion.modulo_requerido is None or definicion.modulo_requerido in modulos


def normalizar(definicion: DefinicionParametro, valor: object) -> str | None:
    """Convierte el valor recibido al texto que se guarda; None si no es válido."""
    if isinstance(valor, bool):  # bool es int en Python: True no debe pasar como 1
        return None
    if definicion.tipo == OPCION:
        opciones = definicion.opciones or ()
        return valor if isinstance(valor, str) and valor in opciones else None

    try:
        numero = Decimal(str(valor).strip())
    except InvalidOperation:
        return None
    if not numero.is_finite():
        return None
    if definicion.tipo == ENTERO:
        if numero != numero.to_integral_value():
            return None
        numero = numero.to_integral_value()
    if definicion.minimo is not None and numero < definicion.minimo:
        return None
    if definicion.maximo is not None and numero > definicion.maximo:
        return None
    return str(int(numero)) if definicion.tipo == ENTERO else format(numero.normalize(), "f")


def convertir_para_nodo(definicion: DefinicionParametro, valor: str) -> int | float | str:
    """Tipo nativo de JSON para el ESP32: número para enteros y decimales, texto para opciones."""
    if definicion.tipo == ENTERO:
        return int(valor)
    if definicion.tipo == DECIMAL:
        return float(valor)
    return valor


def problemas_entre_parametros(valores: dict[str, str]) -> list[Problema]:
    problemas = []
    for menor, mayor in REGLAS_ENTRE_PARAMETROS:
        if (
            menor in valores
            and mayor in valores
            and Decimal(valores[menor]) >= Decimal(valores[mayor])
        ):
            problemas.append(Problema(menor, f"DEBE_SER_MENOR_QUE_{mayor}"))
    return problemas
