"""GET /health: estado del servidor y de la base, sin sesión."""

from fastapi import APIRouter, Response, status

from app.api.deps import SesionBD
from app.esquemas.salud import EstadoSalud
from app.servicios.salud import consultar_salud

router = APIRouter(tags=["salud"])


@router.get(
    "/health",
    response_model=EstadoSalud,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": EstadoSalud}},
)
def health(sesion: SesionBD, respuesta: Response) -> EstadoSalud:
    estado = consultar_salud(sesion)
    if estado.base_de_datos != "conectada":
        respuesta.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return estado
