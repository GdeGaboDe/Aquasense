"""Alta y edición de nodos: /api/v1/nodos."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status

from app.api.deps import SesionBD, UsuarioSesion, obtener_usuario_actual
from app.api.seguridad import limitar_api_web
from app.esquemas.control import ParametrosEditar, ParametrosNodo
from app.esquemas.web import NodoCreado, NodoCrear, NodoEditar, NodoSalida
from app.modelos import Nodo
from app.servicios import instalacion as servicio
from app.servicios import parametros as servicio_parametros

router = APIRouter(
    prefix="/api/v1/nodos",
    tags=["nodos"],
    dependencies=[Depends(limitar_api_web), Depends(obtener_usuario_actual)],
)


@router.post("", response_model=NodoCreado, status_code=status.HTTP_201_CREATED)
def crear(datos: NodoCrear, sesion: SesionBD) -> NodoCreado:
    nodo, token = servicio.crear_nodo(sesion, datos)
    return NodoCreado(**NodoSalida.model_validate(nodo).model_dump(), token=token)


@router.patch("/{nodo_id}", response_model=NodoSalida)
def editar(nodo_id: int, datos: NodoEditar, sesion: SesionBD) -> Nodo:
    return servicio.editar_nodo(sesion, nodo_id, datos)


@router.get("/{nodo_id}/parametros", response_model=ParametrosNodo)
def obtener_parametros(nodo_id: int, sesion: SesionBD) -> ParametrosNodo:
    return servicio_parametros.obtener(sesion, nodo_id)


@router.put("/{nodo_id}/parametros", response_model=ParametrosNodo)
def actualizar_parametros(
    nodo_id: int, datos: ParametrosEditar, usuario: UsuarioSesion, sesion: SesionBD
) -> ParametrosNodo:
    return servicio_parametros.actualizar(sesion, nodo_id, datos, usuario, datetime.now(UTC))
