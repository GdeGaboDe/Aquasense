"""Tablas de SQLAlchemy. Importar aquí cada modelo para que Alembic lo vea."""

from app.modelos.actividad import (
    CambioAgua,
    Comando,
    Dosis,
    EstadoComando,
    Lectura,
    OrigenDosis,
    OrigenHora,
    Prediccion,
    TipoComando,
)
from app.modelos.base import Base
from app.modelos.catalogos import Parametro, Severidad, TipoAlerta, TipoVariable, Variable
from app.modelos.control import Alerta, Umbral, ValorParametro
from app.modelos.instalacion import Nodo, NodoModulo, Sensor, Tanque, Usuario

__all__ = [
    "Alerta",
    "Base",
    "CambioAgua",
    "Comando",
    "Dosis",
    "EstadoComando",
    "Lectura",
    "Nodo",
    "NodoModulo",
    "OrigenDosis",
    "OrigenHora",
    "Parametro",
    "Prediccion",
    "Sensor",
    "Severidad",
    "Tanque",
    "TipoAlerta",
    "TipoComando",
    "TipoVariable",
    "Umbral",
    "Usuario",
    "ValorParametro",
    "Variable",
]
