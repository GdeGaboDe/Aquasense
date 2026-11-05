"""Tablas de SQLAlchemy. Importar aquí cada modelo para que Alembic lo vea."""

from app.modelos.actividad import (
    CambioAgua,
    Comando,
    Dosis,
    EstadoComando,
    Lectura,
    OrigenDosis,
    OrigenHora,
    TipoComando,
)
from app.modelos.base import Base
from app.modelos.catalogos import Parametro, Severidad, TipoAlerta, TipoVariable, Variable
from app.modelos.instalacion import Nodo, NodoModulo, Sensor, Tanque, Usuario

__all__ = [
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
    "Sensor",
    "Severidad",
    "Tanque",
    "TipoAlerta",
    "TipoComando",
    "TipoVariable",
    "Usuario",
    "Variable",
]
