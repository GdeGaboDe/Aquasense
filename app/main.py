"""Punto de entrada: crea la aplicación FastAPI, sus middlewares y sus rutas."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import alertas, auth, comandos, dispositivo, nodos, salud, tanques
from app.api.errores import registrar_manejadores
from app.api.seguridad import EncabezadosDeSeguridad, limitador
from app.config import Settings, obtener_settings
from app.registro import configurar_registro

_DIRECTORIO_WEB = Path(__file__).resolve().parent.parent / "web"
_SEGUNDOS_POR_HORA = 3600


def crear_app(settings: Settings) -> FastAPI:
    docs_activas = settings.docs_publicas
    app = FastAPI(
        title="AquaSense",
        docs_url="/docs" if docs_activas else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_activas else None,
    )
    app.state.limiter = limitador
    registrar_manejadores(app)

    # El último en agregarse es el primero en ejecutarse.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="aquasense_sesion",
        max_age=settings.sesion_horas * _SEGUNDOS_POR_HORA,
        same_site="strict",
        https_only=False,  # EncabezadosDeSeguridad agrega Secure cuando la petición llega por HTTPS
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.hosts_permitidos)
    app.add_middleware(EncabezadosDeSeguridad)

    for modulo in (salud, dispositivo, auth, tanques, nodos, alertas, comandos):
        app.include_router(modulo.router)
    # Al final: el montaje en "/" atrapa toda ruta que no sea de la API.
    app.mount("/", StaticFiles(directory=_DIRECTORIO_WEB, html=True), name="web")
    return app


configurar_registro()
app = crear_app(obtener_settings())
