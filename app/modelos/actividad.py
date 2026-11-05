"""Lo que ocurre en cada tanque: lecturas, comandos, dosis y cambios de agua."""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base
from app.modelos.tipos import DECIMAL_VALOR, FechaUTC, enum_por_valor


class OrigenHora(enum.StrEnum):
    SERVIDOR = "servidor"
    NTP = "ntp"
    DESCONOCIDA = "desconocida"


class TipoComando(enum.StrEnum):
    DISPENSAR = "DISPENSAR"
    SILENCIAR_ALARMA = "SILENCIAR_ALARMA"
    AIREADOR = "AIREADOR"


class EstadoComando(enum.StrEnum):
    PENDIENTE = "pendiente"
    ENTREGADO = "entregado"
    CONFIRMADO = "confirmado"
    FALLIDO = "fallido"
    EXPIRADO = "expirado"


class OrigenDosis(enum.StrEnum):
    REMOTO = "remoto"
    AUTOMATICO = "automatico"
    LOCAL = "local"


class Lectura(Base):
    __tablename__ = "lectura"

    # La llave compuesta impide duplicar lecturas reenviadas desde LittleFS.
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensor.id"), primary_key=True)
    medido_en: Mapped[datetime] = mapped_column(FechaUTC, primary_key=True)
    valor: Mapped[Decimal] = mapped_column(DECIMAL_VALOR)
    recibido_en: Mapped[datetime] = mapped_column(FechaUTC)
    origen_hora: Mapped[OrigenHora] = mapped_column(enum_por_valor(OrigenHora, "origen_hora"))


class Comando(Base):
    __tablename__ = "comando"
    __table_args__ = (Index(None, "nodo_id", "estado"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nodo_id: Mapped[int] = mapped_column(ForeignKey("nodo.id"))
    tipo: Mapped[TipoComando] = mapped_column(enum_por_valor(TipoComando, "tipo_comando"))
    argumento: Mapped[int | None] = mapped_column(Integer)
    estado: Mapped[EstadoComando] = mapped_column(enum_por_valor(EstadoComando, "estado_comando"))
    creado_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(FechaUTC)
    expira_en: Mapped[datetime] = mapped_column(FechaUTC)
    entregado_en: Mapped[datetime | None] = mapped_column(FechaUTC)
    resuelto_en: Mapped[datetime | None] = mapped_column(FechaUTC)
    detalle: Mapped[str | None] = mapped_column(String(200))


class Dosis(Base):
    __tablename__ = "dosis"
    # Esta única también sirve como el índice (nodo_id, dosificada_en) que pide la sección 5.2.
    __table_args__ = (
        UniqueConstraint("nodo_id", "dosificada_en"),
        CheckConstraint("cargas > 0", name="cargas_positivas"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nodo_id: Mapped[int] = mapped_column(ForeignKey("nodo.id"))
    cargas: Mapped[int] = mapped_column(Integer)
    origen: Mapped[OrigenDosis] = mapped_column(enum_por_valor(OrigenDosis, "origen_dosis"))
    dosificada_en: Mapped[datetime] = mapped_column(FechaUTC)
    comando_id: Mapped[int | None] = mapped_column(ForeignKey("comando.id"), unique=True)


class CambioAgua(Base):
    __tablename__ = "cambio_agua"
    __table_args__ = (
        CheckConstraint("porcentaje > 0 AND porcentaje <= 100", name="porcentaje_valido"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tanque_id: Mapped[int] = mapped_column(ForeignKey("tanque.id"))
    realizado_en: Mapped[datetime] = mapped_column(FechaUTC)
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    registrado_por: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
