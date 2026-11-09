"""Predicción del cambio de agua por regresión lineal del TDS (CLAUDE.md, 7.5).

Todo es puro: recibe fechas y lecturas, nunca consulta el reloj ni la base.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise

import numpy as np

MODELO_VERSION = "lineal-1"
MIN_HORAS_DE_DATOS = 24.0
MIN_MUESTRAS = 50
HORAS_POR_DIA = 24.0
SEGUNDOS_POR_HORA = 3600.0
# En la evaluación, una predicción por cada día de datos del ciclo evaluado.
PASO_EVALUACION = timedelta(days=1)

# Una pendiente menor que esto es ruido de redondeo, no una tendencia.
PENDIENTE_MINIMA_PPM_H = 1e-6
# Un cruce más lejano no es una estimación útil y además desborda las fechas.
HORIZONTE_MAXIMO = timedelta(days=3650)

MOTIVO_POCOS_DATOS = "DATOS_INSUFICIENTES"
MOTIVO_PENDIENTE_NO_POSITIVA = "PENDIENTE_NO_POSITIVA"


@dataclass(frozen=True)
class Ajuste:
    pendiente_ppm_h: float
    intercepto_ppm: float  # valor estimado al iniciar el ciclo
    r2: float | None
    n_muestras: int
    horas_de_datos: float


@dataclass(frozen=True)
class Ciclo:
    """Un ciclo completo: del cambio de agua `inicio` al siguiente, `fin`."""

    inicio: datetime
    fin: datetime
    lecturas: Sequence[tuple[datetime, float]]


@dataclass(frozen=True)
class Evaluacion:
    mae_modelo_dias: float | None
    mae_baseline_dias: float | None
    predicciones_evaluadas: int


def _horas_desde(inicio: datetime, momento: datetime) -> float:
    return (momento - inicio).total_seconds() / SEGUNDOS_POR_HORA


def ajustar(inicio_ciclo: datetime, lecturas: Sequence[tuple[datetime, float]]) -> Ajuste | None:
    """Regresión de TDS contra horas desde el cambio de agua; None si no hay datos suficientes."""
    if len(lecturas) < MIN_MUESTRAS:
        return None
    horas = np.array([_horas_desde(inicio_ciclo, momento) for momento, _ in lecturas])
    valores = np.array([valor for _, valor in lecturas], dtype=float)
    horas_de_datos = float(horas.max() - horas.min())
    if horas_de_datos < MIN_HORAS_DE_DATOS:
        return None
    pendiente, intercepto = np.polyfit(horas, valores, 1)
    residuos = valores - (pendiente * horas + intercepto)
    variacion = float(np.sum((valores - valores.mean()) ** 2))
    r2 = None if variacion == 0 else 1 - float(np.sum(residuos**2)) / variacion
    return Ajuste(float(pendiente), float(intercepto), r2, len(lecturas), horas_de_datos)


def momento_de_cruce(inicio_ciclo: datetime, ajuste: Ajuste, limite: float) -> datetime | None:
    """Cuándo la recta alcanza el límite. None si no sube o si el cruce está fuera de horizonte."""
    if ajuste.pendiente_ppm_h <= PENDIENTE_MINIMA_PPM_H:
        return None
    horas = (limite - ajuste.intercepto_ppm) / ajuste.pendiente_ppm_h
    if horas > HORIZONTE_MAXIMO.total_seconds() / SEGUNDOS_POR_HORA:
        return None
    return inicio_ciclo + timedelta(hours=horas)


def dias_restantes(cruce: datetime, ahora: datetime) -> float:
    """Días hasta el cruce; 0 si ya se superó el límite."""
    return max(0.0, (cruce - ahora).total_seconds() / (SEGUNDOS_POR_HORA * HORAS_POR_DIA))


def duracion_promedio_dias(cambios: Sequence[datetime]) -> float | None:
    """Baseline: duración promedio de los ciclos completos entre cambios de agua consecutivos."""
    ordenados = sorted(cambios)
    if len(ordenados) < 2:
        return None
    duraciones = [
        (fin - inicio).total_seconds() / (SEGUNDOS_POR_HORA * HORAS_POR_DIA)
        for inicio, fin in pairwise(ordenados)
    ]
    return sum(duraciones) / len(duraciones)


def evaluar(ciclos: Sequence[Ciclo], limite: float) -> Evaluacion | None:
    """MAE en días del modelo y del baseline sobre el último ciclo completo.

    División cronológica, nunca aleatoria: el baseline solo conoce los ciclos anteriores al
    evaluado, y cada predicción del modelo solo usa lecturas hasta su punto de corte.
    """
    if not ciclos:
        return None
    ordenados = sorted(ciclos, key=lambda c: c.inicio)
    evaluado, anteriores = ordenados[-1], ordenados[:-1]
    duracion_baseline = duracion_promedio_dias(
        [c.inicio for c in anteriores] + ([anteriores[-1].fin] if anteriores else [])
    )
    lecturas = sorted(evaluado.lecturas)

    errores_modelo: list[float] = []
    errores_baseline: list[float] = []
    corte = evaluado.inicio + PASO_EVALUACION
    while corte < evaluado.fin:
        disponibles = [x for x in lecturas if x[0] <= corte]
        ajuste = ajustar(evaluado.inicio, disponibles)
        cruce = momento_de_cruce(evaluado.inicio, ajuste, limite) if ajuste else None
        if cruce is not None:
            errores_modelo.append(abs((cruce - evaluado.fin).total_seconds()) / 86400)
            if duracion_baseline is not None:
                estimado = evaluado.inicio + timedelta(days=duracion_baseline)
                errores_baseline.append(abs((estimado - evaluado.fin).total_seconds()) / 86400)
        corte += PASO_EVALUACION

    if not errores_modelo:
        return None
    return Evaluacion(
        mae_modelo_dias=sum(errores_modelo) / len(errores_modelo),
        mae_baseline_dias=sum(errores_baseline) / len(errores_baseline)
        if errores_baseline
        else None,
        predicciones_evaluadas=len(errores_modelo),
    )
