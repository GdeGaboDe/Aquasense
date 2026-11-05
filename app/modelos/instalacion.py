"""Cuentas y equipo instalado: usuario, tanque, nodo, módulos y sensores."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.modelos.base import Base
from app.modelos.tipos import FechaUTC


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(String(60), unique=True)
    hash_contrasena: Mapped[str] = mapped_column(String(60))
    # Sube al cerrar sesión: las cookies firmadas con un valor anterior dejan de ser válidas.
    sesion_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    creado_en: Mapped[datetime] = mapped_column(FechaUTC)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(FechaUTC)


class Tanque(Base):
    __tablename__ = "tanque"
    __table_args__ = (CheckConstraint("volumen_l > 0", name="volumen_positivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    volumen_l: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    especie: Mapped[str | None] = mapped_column(String(80))
    notas: Mapped[str | None] = mapped_column(String(500))


class Nodo(Base):
    __tablename__ = "nodo"
    __table_args__ = (
        CheckConstraint(
            "(padre_id IS NULL AND token_hash IS NOT NULL) "
            "OR (padre_id IS NOT NULL AND token_hash IS NULL)",
            name="token_solo_en_autonomo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mac: Mapped[str] = mapped_column(String(17), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    tanque_id: Mapped[int] = mapped_column(ForeignKey("tanque.id"), unique=True)
    padre_id: Mapped[int | None] = mapped_column(ForeignKey("nodo.id"))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    firmware: Mapped[str | None] = mapped_column(String(20))
    boot_actual: Mapped[int | None] = mapped_column(Integer)
    config_version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    config_version_aplicada: Mapped[int | None] = mapped_column(Integer)
    ultimo_contacto: Mapped[datetime | None] = mapped_column(FechaUTC)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))


class NodoModulo(Base):
    """Módulos que el nodo anunció en su último lote.

    `sensor` no alcanza: `servo` y `rtc` no reportan variables, y aun así hay que saber si
    el nodo los tiene para permitir comandos y filtrar parámetros.
    """

    __tablename__ = "nodo_modulo"

    nodo_id: Mapped[int] = mapped_column(ForeignKey("nodo.id"), primary_key=True)
    modulo: Mapped[str] = mapped_column(String(20), primary_key=True)
    detectado_en: Mapped[datetime] = mapped_column(FechaUTC)


class Sensor(Base):
    __tablename__ = "sensor"
    __table_args__ = (UniqueConstraint("nodo_id", "variable_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nodo_id: Mapped[int] = mapped_column(ForeignKey("nodo.id"))
    variable_id: Mapped[int] = mapped_column(ForeignKey("variable.id"))
    detectado_en: Mapped[datetime] = mapped_column(FechaUTC)
    ultimo_visto: Mapped[datetime] = mapped_column(FechaUTC)
