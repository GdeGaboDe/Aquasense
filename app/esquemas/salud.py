"""Contrato de salida de GET /health."""

from typing import Literal

from pydantic import BaseModel


class EstadoSalud(BaseModel):
    estado: Literal["ok", "degradado"]
    base_de_datos: Literal["conectada", "sin_conexion"]
