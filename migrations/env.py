"""Entorno de Alembic. Migra con el usuario de MIGRACIONES_DATABASE_URL, no con el de la app."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import obtener_settings
from app.modelos import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

metadata_objetivo = Base.metadata


def ejecutar_migraciones() -> None:
    engine = create_engine(obtener_settings().migraciones_database_url)
    with engine.connect() as conexion:
        context.configure(connection=conexion, target_metadata=metadata_objetivo)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("AquaSense no usa migraciones en modo offline.")

ejecutar_migraciones()
