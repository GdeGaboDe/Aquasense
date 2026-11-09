"""Bitácora de alimentación de un tanque."""

from fastapi import status
from sqlalchemy.orm import Session

from app.esquemas.control import DosisSalida, Pagina
from app.modelos import Tanque
from app.repositorios import control as repo
from app.repositorios.instalacion import buscar_nodo_de_tanque
from app.servicios.errores import ErrorDeNegocio


def listar(sesion: Session, tanque_id: int, pagina: int, tamano: int) -> Pagina[DosisSalida]:
    if sesion.get(Tanque, tanque_id) is None:
        raise ErrorDeNegocio(
            status.HTTP_404_NOT_FOUND, "TANQUE_NO_ENCONTRADO", "No existe ese tanque."
        )
    nodo = buscar_nodo_de_tanque(sesion, tanque_id)
    if nodo is None:
        return Pagina(elementos=[], total=0, pagina=pagina, tamano=tamano)
    filas, total = repo.listar_dosis(sesion, nodo.id, (pagina - 1) * tamano, tamano)
    elementos = [
        DosisSalida(
            id=d.id,
            nodo_id=d.nodo_id,
            cargas=d.cargas,
            origen=d.origen.value,
            dosificada_en=d.dosificada_en,
            comando_id=d.comando_id,
        )
        for d in filas
    ]
    return Pagina(elementos=elementos, total=total, pagina=pagina, tamano=tamano)
