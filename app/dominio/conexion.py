"""Estado de conexión de un nodo, calculado al consultar (CLAUDE.md, 7.2)."""

from datetime import datetime, timedelta

CADENCIA_TELEMETRIA = timedelta(seconds=10)
LIMITE_SIN_REPORTAR = 3 * CADENCIA_TELEMETRIA


def esta_sin_conexion(ultimo_contacto: datetime | None, ahora: datetime) -> bool:
    if ultimo_contacto is None:
        return True
    return ahora - ultimo_contacto > LIMITE_SIN_REPORTAR
