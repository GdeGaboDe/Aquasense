"""Tablas de SQLAlchemy. Importar aquí cada modelo para que Alembic lo vea."""

from app.modelos.base import Base
from app.modelos.catalogos import Parametro, TipoAlerta, Variable

__all__ = ["Base", "Parametro", "TipoAlerta", "Variable"]
