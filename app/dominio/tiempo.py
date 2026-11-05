"""Asignación de `medido_en` a lecturas y eventos (CLAUDE.md, 7.1)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

ORIGEN_SERVIDOR = "servidor"
ORIGEN_NTP = "ntp"
ORIGEN_DESCONOCIDA = "desconocida"

_TOLERANCIA_FUTURO = timedelta(seconds=60)
_EPOCH_MINIMO = datetime(2026, 1, 1, tzinfo=UTC)
_MS_POR_SEGUNDO = 1000


@dataclass(frozen=True)
class HoraAsignada:
    medido_en: datetime
    origen: str


def redondear_a_ms(momento: datetime) -> datetime:
    milisegundos = round(momento.microsecond / _MS_POR_SEGUNDO)
    # Se suma como intervalo porque 999.6 ms redondea al segundo siguiente.
    return momento.replace(microsecond=0) + timedelta(milliseconds=milisegundos)


def _epoch_valido(epoch_ms: int | None, recibido_en: datetime) -> datetime | None:
    if epoch_ms is None:
        return None
    try:
        momento = datetime.fromtimestamp(epoch_ms / _MS_POR_SEGUNDO, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
    if momento < _EPOCH_MINIMO or momento > recibido_en + _TOLERANCIA_FUTURO:
        return None
    return momento


def asignar_hora(
    recibido_en: datetime,
    boot_actual: int | None,
    boot_lectura: int,
    edad_ms: int,
    epoch_ms: int | None,
) -> HoraAsignada:
    """Decide la hora de una medición.

    Args:
        recibido_en: hora UTC del servidor al recibir el lote.
        boot_actual: contador de arranques del autónomo en este lote; None si no lo anunció.
        boot_lectura: contador de arranques del autónomo cuando se midió el dato.
        edad_ms: milisegundos transcurridos entre la medición y el envío.
        epoch_ms: hora Unix de la medición si el autónomo tenía NTP; si no, None.
    """
    if boot_lectura == boot_actual:
        momento = recibido_en - timedelta(milliseconds=edad_ms)
        return HoraAsignada(redondear_a_ms(momento), ORIGEN_SERVIDOR)

    momento_ntp = _epoch_valido(epoch_ms, recibido_en)
    if momento_ntp is not None:
        return HoraAsignada(redondear_a_ms(momento_ntp), ORIGEN_NTP)

    return HoraAsignada(redondear_a_ms(recibido_en), ORIGEN_DESCONOCIDA)
