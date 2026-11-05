"""Formato único de error: {"error": {"code", "message", "details"}} (CLAUDE.md, 6.4)."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException

from app.api.seguridad import ENCABEZADOS_BASE
from app.servicios.errores import ErrorDeNegocio

logger = logging.getLogger(__name__)


def _respuesta(codigo_http: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=codigo_http,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDeNegocio)
    def _negocio(_: Request, error: ErrorDeNegocio) -> JSONResponse:
        return _respuesta(error.codigo_http, error.code, error.message, error.details)

    @app.exception_handler(RequestValidationError)
    def _validacion(_: Request, error: RequestValidationError) -> JSONResponse:
        # Solo ubicación y tipo: el valor recibido podría ser una contraseña o un token.
        detalles = [{"campo": e["loc"], "tipo": e["type"]} for e in error.errors()]
        return _respuesta(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "DATOS_INVALIDOS",
            "Los datos enviados no cumplen el formato esperado.",
            detalles,
        )

    @app.exception_handler(RateLimitExceeded)
    def _limite(_: Request, __: RateLimitExceeded) -> JSONResponse:
        return _respuesta(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "DEMASIADAS_PETICIONES",
            "Demasiadas peticiones. Espera un momento e inténtalo de nuevo.",
        )

    @app.exception_handler(HTTPException)
    def _http(_: Request, error: HTTPException) -> JSONResponse:
        return _respuesta(
            error.status_code,
            HTTPStatus(error.status_code).name,
            HTTPStatus(error.status_code).phrase,
        )

    @app.exception_handler(Exception)
    def _inesperado(request: Request, error: Exception) -> JSONResponse:
        logger.error(
            "Error inesperado en %s %s: %s",
            request.method,
            request.url.path,
            type(error).__name__,
        )
        respuesta = _respuesta(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "ERROR_INTERNO",
            "Ocurrió un error interno.",
        )
        # Este manejador corre por fuera de los middlewares: no pasaría por los encabezados.
        respuesta.headers.update(ENCABEZADOS_BASE)
        return respuesta
