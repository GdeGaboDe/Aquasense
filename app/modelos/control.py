"""Umbrales, alertas y valores de parámetros por nodo (Fase 2)."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base
from app.modelos.tipos import DECIMAL_VALOR, FechaUTC


class Umbral(Base):
    __tablename__ = "umbral"
    __table_args__ = (
        CheckConstraint("minimo < maximo", name="rango"),
        CheckConstraint("histeresis >= 0", name="histeresis_no_negativa"),
    )

    tanque_id: Mapped[int] = mapped_column(ForeignKey("tanque.id"), primary_key=True)
    variable_id: Mapped[int] = mapped_column(ForeignKey("variable.id"), primary_key=True)
    minimo: Mapped[Decimal | None] = mapped_column(DECIMAL_VALOR)
    maximo: Mapped[Decimal | None] = mapped_column(DECIMAL_VALOR)
    histeresis: Mapped[Decimal] = mapped_column(DECIMAL_VALOR)


class Alerta(Base):
    """Alerta de un tanque; `resuelta_en` nulo significa que sigue activa.

    MySQL no tiene índices parciales: las dos columnas generadas permiten que la base misma
    impida dos alertas activas iguales. `activa` es NULL al resolverse, y los NULL no chocan en
    un índice único; `variable_clave` evita que un `variable_id` nulo escape de la regla.
    """

    __tablename__ = "alerta"
    __table_args__ = (
        UniqueConstraint("tanque_id", "tipo_alerta_id", "variable_clave", "activa"),
        Index(None, "tanque_id", "resuelta_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tanque_id: Mapped[int] = mapped_column(ForeignKey("tanque.id"))
    nodo_id: Mapped[int | None] = mapped_column(ForeignKey("nodo.id"))
    tipo_alerta_id: Mapped[int] = mapped_column(ForeignKey("tipo_alerta.id"))
    variable_id: Mapped[int | None] = mapped_column(ForeignKey("variable.id"))
    valor: Mapped[Decimal | None] = mapped_column(DECIMAL_VALOR)
    iniciada_en: Mapped[datetime] = mapped_column(FechaUTC)
    resuelta_en: Mapped[datetime | None] = mapped_column(FechaUTC)
    variable_clave: Mapped[int] = mapped_column(Computed("coalesce(variable_id, 0)"))
    activa: Mapped[int | None] = mapped_column(Computed("CASE WHEN resuelta_en IS NULL THEN 1 END"))


class ValorParametro(Base):
    __tablename__ = "valor_parametro"

    nodo_id: Mapped[int] = mapped_column(ForeignKey("nodo.id"), primary_key=True)
    parametro_id: Mapped[int] = mapped_column(ForeignKey("parametro.id"), primary_key=True)
    valor: Mapped[str] = mapped_column(String(40))
    modificado_en: Mapped[datetime] = mapped_column(FechaUTC)
    modificado_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
