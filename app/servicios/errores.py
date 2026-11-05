"""Errores que los servicios comunican a la capa HTTP sin depender de FastAPI."""

from typing import Any


class ErrorDeNegocio(Exception):
    def __init__(self, codigo_http: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.codigo_http = codigo_http
        self.code = code
        self.message = message
        self.details = details
