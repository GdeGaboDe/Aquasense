from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.deps import obtener_sesion
from app.config import obtener_settings
from app.main import crear_app


def _cliente_con_sesion(sesion: MagicMock) -> TestClient:
    app = crear_app(obtener_settings())
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    return TestClient(app)


def test_health_responde_ok_cuando_la_base_contesta():
    cliente = _cliente_con_sesion(MagicMock())

    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "base_de_datos": "conectada"}


def test_health_responde_503_sin_detalles_internos_cuando_la_base_falla():
    sesion = MagicMock()
    sesion.execute.side_effect = OperationalError("SELECT 1", {}, Exception("host secreto"))
    cliente = _cliente_con_sesion(sesion)

    respuesta = cliente.get("/health")

    assert respuesta.status_code == 503
    assert respuesta.json() == {"estado": "degradado", "base_de_datos": "sin_conexion"}
    assert "secreto" not in respuesta.text


def test_docs_responden_404_con_docs_publicas_desactivadas():
    settings = obtener_settings().model_copy(update={"docs_publicas": False})
    cliente = TestClient(crear_app(settings))

    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404


def test_docs_disponibles_con_docs_publicas_activadas():
    settings = obtener_settings().model_copy(update={"docs_publicas": True})
    cliente = TestClient(crear_app(settings))

    assert cliente.get("/docs").status_code == 200
    assert cliente.get("/openapi.json").status_code == 200
