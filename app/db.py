"""Engine y fábrica de sesiones de SQLAlchemy."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import obtener_settings

_TIEMPO_CONEXION_S = 3


@lru_cache
def obtener_engine() -> Engine:
    return create_engine(
        obtener_settings().database_url,
        pool_pre_ping=True,
        # Sin este límite, /health se queda colgado si la base no responde.
        connect_args={"connect_timeout": _TIEMPO_CONEXION_S},
    )


@lru_cache
def obtener_fabrica_sesiones() -> sessionmaker[Session]:
    return sessionmaker(bind=obtener_engine(), expire_on_commit=False)
