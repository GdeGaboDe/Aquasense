"""Engine y fábrica de sesiones de SQLAlchemy."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import obtener_settings

_TIEMPO_CONEXION_S = 3


@lru_cache
def obtener_engine() -> Engine:
    url = make_url(obtener_settings().database_url)
    # Sin este límite, /health se queda colgado si MySQL no responde. SQLite no lo admite.
    opciones = {} if url.get_backend_name() == "sqlite" else {"connect_timeout": _TIEMPO_CONEXION_S}
    return create_engine(url, pool_pre_ping=True, connect_args=opciones)


@lru_cache
def obtener_fabrica_sesiones() -> sessionmaker[Session]:
    return sessionmaker(bind=obtener_engine(), expire_on_commit=False)
