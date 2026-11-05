"""Catálogos del sistema (CLAUDE.md, 5.1 y 5.3)."""

import enum
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, Enum, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base

_DECIMAL = Numeric(10, 3)


class TipoVariable(enum.StrEnum):
    NUMERO = "numero"
    BOOLEANO = "booleano"


class Severidad(enum.StrEnum):
    INFO = "info"
    ADVERTENCIA = "advertencia"
    CRITICA = "critica"


class TipoParametro(enum.StrEnum):
    ENTERO = "entero"
    DECIMAL = "decimal"
    OPCION = "opcion"


def _enum_por_valor(clase: type[enum.StrEnum], nombre: str) -> Enum:
    """Guarda el valor en minúsculas del contrato, no el nombre del miembro de Python."""
    return Enum(clase, name=nombre, values_callable=lambda e: [m.value for m in e])


class Variable(Base):
    __tablename__ = "variable"
    __table_args__ = (CheckConstraint("min_fisico < max_fisico", name="rango_fisico"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    unidad: Mapped[str | None] = mapped_column(String(20))
    tipo: Mapped[TipoVariable] = mapped_column(_enum_por_valor(TipoVariable, "tipo_variable"))
    min_fisico: Mapped[Decimal | None] = mapped_column(_DECIMAL)
    max_fisico: Mapped[Decimal | None] = mapped_column(_DECIMAL)


class TipoAlerta(Base):
    __tablename__ = "tipo_alerta"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    severidad: Mapped[Severidad] = mapped_column(_enum_por_valor(Severidad, "severidad"))


class Parametro(Base):
    __tablename__ = "parametro"
    __table_args__ = (CheckConstraint("minimo < maximo", name="rango"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[TipoParametro] = mapped_column(_enum_por_valor(TipoParametro, "tipo_parametro"))
    unidad: Mapped[str | None] = mapped_column(String(20))
    minimo: Mapped[Decimal | None] = mapped_column(_DECIMAL)
    maximo: Mapped[Decimal | None] = mapped_column(_DECIMAL)
    opciones: Mapped[list[str] | None] = mapped_column(JSON)
    valor_defecto: Mapped[str] = mapped_column(String(40))
    modulo_requerido: Mapped[str | None] = mapped_column(String(20))
