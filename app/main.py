"""Punto de entrada: crea la aplicación FastAPI y monta los routers."""

from fastapi import FastAPI

from app.api import dispositivo, salud
from app.api.errores import registrar_manejadores
from app.config import Settings, obtener_settings


def crear_app(settings: Settings) -> FastAPI:
    docs_activas = settings.docs_publicas
    app = FastAPI(
        title="AquaSense",
        docs_url="/docs" if docs_activas else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_activas else None,
    )
    registrar_manejadores(app)
    app.include_router(salud.router)
    app.include_router(dispositivo.router)
    return app


app = crear_app(obtener_settings())
