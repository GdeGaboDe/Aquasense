"""Agregación de lecturas en intervalos para las gráficas (CLAUDE.md, 8.1)."""

from collections.abc import Iterable
from datetime import datetime, timedelta

INTERVALOS = {"1m": timedelta(minutes=1), "5m": timedelta(minutes=5), "1h": timedelta(hours=1)}
MAX_PUNTOS = 2000


def cantidad_de_intervalos(desde: datetime, hasta: datetime, intervalo: timedelta) -> int:
    return max(0, -(-(hasta - desde) // intervalo))  # división hacia arriba


def intervalo_automatico(desde: datetime, hasta: datetime) -> str:
    """El intervalo más fino que no rebasa el máximo de puntos."""
    for codigo, duracion in INTERVALOS.items():
        if cantidad_de_intervalos(desde, hasta, duracion) <= MAX_PUNTOS:
            return codigo
    return "1h"


def promediar(
    lecturas: Iterable[tuple[datetime, float]], desde: datetime, intervalo: timedelta
) -> list[tuple[datetime, float, int]]:
    """Promedio por intervalo, alineado a `desde`. Devuelve (inicio, promedio, muestras) en orden.

    Los intervalos sin lecturas se omiten: la gráfica muestra el hueco en lugar de inventar datos.
    """
    sumas: dict[int, tuple[float, int]] = {}
    for momento, valor in lecturas:
        indice = (momento - desde) // intervalo
        total, cuenta = sumas.get(indice, (0.0, 0))
        sumas[indice] = (total + valor, cuenta + 1)
    return [
        (desde + indice * intervalo, total / cuenta, cuenta)
        for indice, (total, cuenta) in sorted(sumas.items())
    ]
