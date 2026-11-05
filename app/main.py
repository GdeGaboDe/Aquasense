"""Punto de entrada: crea la aplicación FastAPI y monta los routers."""

from fastapi import FastAPI

from app.api import salud
from app.config import Settings, obtener_settings


def crear_app(settings: Settings) -> FastAPI:
    docs_activas = settings.docs_publicas
    app = FastAPI(
        title="AquaSense",
        docs_url="/docs" if docs_activas else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_activas else None,
    )
    app.include_router(salud.router)
    return app


app = crear_app(obtener_settings())
