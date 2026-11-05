import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, make_url


def _url_de_pruebas() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Define TEST_DATABASE_URL para correr las pruebas de integración.")
    # Estas pruebas borran las tablas: nunca deben apuntar a la base con el historial.
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL debe apuntar a una base cuyo nombre termine en _test.")
    return url


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    _url_de_pruebas()
    return Config("alembic.ini")


@pytest.fixture(scope="session")
def engine(alembic_config: Config) -> Iterator[Engine]:
    """Base migrada una vez por corrida, porque cada migración tarda varios segundos en MySQL.

    Una prueba que cambie el esquema o los datos debe dejarlos como estaban.
    """
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    engine = create_engine(_url_de_pruebas())
    yield engine
    engine.dispose()
    command.downgrade(alembic_config, "base")
