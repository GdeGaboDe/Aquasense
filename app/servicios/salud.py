"""Determina el estado del servidor y de la base."""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.esquemas.salud import EstadoSalud
from app.repositorios.salud import comprobar_conexion

logger = logging.getLogger(__name__)


def consultar_salud(sesion: Session) -> EstadoSalud:
    try:
        comprobar_conexion(sesion)
    except SQLAlchemyError as error:
        # Solo el tipo: el mensaje del driver puede incluir datos de conexión.
        logger.error("La base de datos no responde: %s", type(error).__name__)
        return EstadoSalud(estado="degradado", base_de_datos="sin_conexion")
    return EstadoSalud(estado="ok", base_de_datos="conectada")
