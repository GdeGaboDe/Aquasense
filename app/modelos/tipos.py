"""Tipos de columna compartidos."""

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Dialect, Enum, Numeric
from sqlalchemy.dialects import mysql
from sqlalchemy.types import TypeDecorator

DECIMAL_VALOR = Numeric(10, 3)


class FechaUTC(TypeDecorator[datetime]):
    """DATETIME(3) en UTC. La base lo guarda sin zona; en Python siempre lleva zona."""

    impl = DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql")
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("FechaUTC solo acepta fechas con zona horaria.")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def enum_por_valor(clase: type[enum.StrEnum], nombre: str) -> Enum:
    """Guarda el valor del contrato, no el nombre del miembro de Python."""
    return Enum(clase, name=nombre, values_callable=lambda e: [m.value for m in e])
