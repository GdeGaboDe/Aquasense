"""Dependencias compartidas de la capa HTTP."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import obtener_fabrica_sesiones


def obtener_sesion() -> Iterator[Session]:
    with obtener_fabrica_sesiones()() as sesion:
        yield sesion


SesionBD = Annotated[Session, Depends(obtener_sesion)]
