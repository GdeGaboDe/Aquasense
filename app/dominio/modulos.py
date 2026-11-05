"""Módulos posibles de un nodo y las variables que reporta cada uno (CLAUDE.md, 1.3)."""

from collections.abc import Iterable

VARIABLES_POR_MODULO: dict[str, tuple[str, ...]] = {
    "temp": ("temp_c",),
    "tds": ("tds_ppm",),
    "turbidez": ("turbidez_ntu",),
    "flotador": ("flotador_bajo",),
    "luz": ("nivel_luz_adc", "luz_clase"),
    "tolva": ("distancia_tolva_cm", "tolva_vacia"),
    "servo": (),
    "aireador": ("aireador_encendido",),
    "calentador": ("calentador_encendido",),
    "alarma": ("alarma_activa",),
    "rtc": (),
}


def modulos_conocidos(anunciados: Iterable[str]) -> set[str]:
    """Descarta códigos desconocidos: un firmware más nuevo no debe tumbar el lote completo."""
    return {modulo for modulo in anunciados if modulo in VARIABLES_POR_MODULO}


def variables_de_modulos(modulos: Iterable[str]) -> set[str]:
    return {variable for modulo in modulos for variable in VARIABLES_POR_MODULO.get(modulo, ())}
