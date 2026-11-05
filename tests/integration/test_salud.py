from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api.deps import obtener_sesion
from app.config import obtener_settings
from app.main import crear_app


def test_health_responde_ok_con_una_base_real(engine: Engine):
    def sesion_de_prueba() -> Iterator[Session]:
        with Session(engine) as sesion:
            yield sesion

    app = crear_app(obtener_settings())
    app.dependency_overrides[obtener_sesion] = sesion_de_prueba

    respuesta = TestClient(app).get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "base_de_datos": "conectada"}
