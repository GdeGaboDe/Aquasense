import hashlib
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, delete, make_url
from sqlalchemy.orm import Session

from app.api.deps import obtener_sesion
from app.config import obtener_settings
from app.main import crear_app
from app.modelos import (
    CambioAgua,
    Comando,
    Dosis,
    Lectura,
    Nodo,
    NodoModulo,
    Sensor,
    Tanque,
    Usuario,
)

IP_LAN = "192.168.1.50"
# Del hijo hacia el padre: así ninguna llave foránea impide borrar.
_TABLAS_CON_DATOS_DE_PRUEBA = (
    Lectura,
    Sensor,
    NodoModulo,
    Dosis,
    Comando,
    CambioAgua,
    Nodo,
    Tanque,
    Usuario,
)


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


@pytest.fixture
def sesion(engine: Engine) -> Iterator[Session]:
    """Sesión para preparar y revisar datos; al terminar deja las tablas vacías."""
    with Session(engine, expire_on_commit=False) as sesion:
        yield sesion
        sesion.rollback()
        for tabla in _TABLAS_CON_DATOS_DE_PRUEBA:
            if tabla is Nodo:
                # Los satélites referencian a su autónomo dentro de la misma tabla.
                sesion.execute(delete(Nodo).where(Nodo.padre_id.is_not(None)))
            sesion.execute(delete(tabla))
        sesion.commit()


@pytest.fixture
def crear_cliente(engine: Engine) -> Callable[..., TestClient]:
    def fabrica(ip: str = IP_LAN) -> TestClient:
        def sesion_de_prueba() -> Iterator[Session]:
            with Session(engine, expire_on_commit=False) as sesion:
                yield sesion

        app = crear_app(obtener_settings())
        app.dependency_overrides[obtener_sesion] = sesion_de_prueba
        return TestClient(app, client=(ip, 50000))

    return fabrica


@pytest.fixture
def cliente(crear_cliente: Callable[..., TestClient], sesion: Session) -> TestClient:
    return crear_cliente()


@dataclass(frozen=True)
class NodoDePrueba:
    id: int
    mac: str
    token: str | None
    tanque_id: int


@pytest.fixture
def crear_nodo(sesion: Session) -> Callable[..., NodoDePrueba]:
    contador = iter(range(1, 100))

    def fabrica(padre_id: int | None = None) -> NodoDePrueba:
        numero = next(contador)
        tanque = Tanque(nombre=f"Tanque {numero}", volumen_l=20)
        sesion.add(tanque)
        sesion.flush()
        token = None if padre_id else f"token-de-prueba-{numero}"
        nodo = Nodo(
            mac=f"24:6F:28:00:00:{numero:02X}",
            nombre=f"Nodo {numero}",
            tanque_id=tanque.id,
            padre_id=padre_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest() if token else None,
        )
        sesion.add(nodo)
        sesion.commit()
        return NodoDePrueba(nodo.id, nodo.mac, token, tanque.id)

    return fabrica
