"""Consulta mínima para saber si la base responde."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def comprobar_conexion(sesion: Session) -> None:
    sesion.execute(text("SELECT 1"))
