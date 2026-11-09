"""Contratos de series para gráficas, cambios de agua y predicción."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.esquemas.web import FechaIso


class PuntoSerie(BaseModel):
    t: FechaIso
    valor: float
    muestras: int


class Serie(BaseModel):
    variable: str
    nombre: str
    unidad: str | None
    tipo: Literal["numero", "booleano"]
    intervalo: Literal["1m", "5m", "1h"]
    desde: FechaIso
    hasta: FechaIso
    puntos: list[PuntoSerie]


class CambioAguaCrear(BaseModel):
    porcentaje: Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]
    # Si no se indica, es ahora. Siempre en UTC o con zona: nunca hora local sin zona.
    realizado_en: AwareDatetime | None = None


class CambioAguaSalida(BaseModel):
    id: int
    tanque_id: int
    realizado_en: FechaIso
    porcentaje: float
    registrado_por: int


class EvaluacionSalida(BaseModel):
    mae_modelo_dias: float | None
    mae_baseline_dias: float | None
    predicciones_evaluadas: int


class PrediccionSalida(BaseModel):
    estado: Literal["confiable", "no_confiable"]
    motivo: str | None
    ciclo_iniciado_en: FechaIso
    dias_transcurridos: float
    dias_restantes: float | None
    fecha_estimada: FechaIso | None
    baseline_dias: float | None
    baseline_dias_restantes: float | None
    limite_tds: float | None
    pendiente_ppm_por_dia: float | None
    r2: float | None
    n_muestras: int
    horas_de_datos: float
    modelo_version: str
    generada_en: FechaIso | None
    evaluacion: EvaluacionSalida | None
