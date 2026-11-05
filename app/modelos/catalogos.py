"""Catálogos del sistema (CLAUDE.md, 5.1 y 5.3)."""

import enum
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base
from app.modelos.tipos import DECIMAL_VALOR, enum_por_valor


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


class Variable(Base):
    __tablename__ = "variable"
    __table_args__ = (CheckConstraint("min_fisico < max_fisico", name="rango_fisico"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    unidad: Mapped[str | None] = mapped_column(String(20))
    tipo: Mapped[TipoVariable] = mapped_column(enum_por_valor(TipoVariable, "tipo_variable"))
    min_fisico: Mapped[Decimal | None] = mapped_column(DECIMAL_VALOR)
    max_fisico: Mapped[Decimal | None] = mapped_column(DECIMAL_VALOR)


class TipoAlerta(Base):
    __tablename__ = "tipo_alerta"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    severidad: Mapped[Severidad] = mapped_column(enum_por_valor(Severidad, "severidad"))


class Parametro(Base):
    __tablename__ = "parametro"
    __table_args__ = (CheckConstraint("minimo < maximo", name="rango"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[TipoParametro] = mapped_column(enum_por_valor(TipoParametro, "tipo_parametro"))
    unidad: Mapped[str | None] = mapped_column(String(20))
    minimo: Mapped[Decimal | None] = mapped_column(DECIMAL_VALOR)
    maximo: Mapped[Decimal | None] = mapped_column(DECIMAL_VALOR)
    opciones: Mapped[list[str] | None] = mapped_column(JSON)
    valor_defecto: Mapped[str] = mapped_column(String(40))
    modulo_requerido: Mapped[str | None] = mapped_column(String(20))
