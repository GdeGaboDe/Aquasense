from datetime import UTC, datetime, timedelta

import pytest

from app.dominio.comandos import (
    TransicionInvalida,
    bloquea_otro_dispensar,
    estado_a_aplicar,
    estado_mostrado,
    motivo_comando_invalido,
    puede_pasar,
)

AHORA = datetime(2026, 11, 20, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("desde", "hacia"),
    [
        ("pendiente", "entregado"),
        ("pendiente", "expirado"),
        ("entregado", "confirmado"),
        ("entregado", "fallido"),
    ],
)
def test_transiciones_validas(desde, hacia):
    assert puede_pasar(desde, hacia)


@pytest.mark.parametrize(
    ("desde", "hacia"),
    [
        ("pendiente", "confirmado"),
        ("entregado", "pendiente"),
        ("entregado", "expirado"),
        ("confirmado", "fallido"),
        ("expirado", "entregado"),
        ("fallido", "confirmado"),
    ],
)
def test_transiciones_invalidas(desde, hacia):
    assert not puede_pasar(desde, hacia)


def test_ack_de_un_comando_entregado_lo_resuelve():
    assert estado_a_aplicar("entregado", "confirmado") == "confirmado"


def test_repetir_el_mismo_ack_no_cambia_nada():
    assert estado_a_aplicar("confirmado", "confirmado") is None


def test_ack_contradictorio_es_una_transicion_invalida():
    with pytest.raises(TransicionInvalida):
        estado_a_aplicar("confirmado", "fallido")


def test_ack_de_un_comando_expirado_es_invalido():
    with pytest.raises(TransicionInvalida):
        estado_a_aplicar("expirado", "confirmado")


@pytest.mark.parametrize(
    ("tipo", "argumento", "modulos", "motivo"),
    [
        ("DISPENSAR", 2, {"servo"}, None),
        ("DISPENSAR", 6, {"servo"}, "ARGUMENTO_INVALIDO"),
        ("DISPENSAR", 0, {"servo"}, "ARGUMENTO_INVALIDO"),
        ("DISPENSAR", None, {"servo"}, "ARGUMENTO_INVALIDO"),
        ("DISPENSAR", 2, {"temp"}, "MODULO_NO_DISPONIBLE"),
        ("SILENCIAR_ALARMA", 60, {"alarma"}, None),
        ("SILENCIAR_ALARMA", 61, {"alarma"}, "ARGUMENTO_INVALIDO"),
        ("AIREADOR", 0, {"aireador"}, None),
        ("AIREADOR", 2, {"aireador"}, "ARGUMENTO_INVALIDO"),
        ("REINICIAR", 1, {"servo"}, "TIPO_DESCONOCIDO"),
    ],
)
def test_valida_tipo_argumento_y_modulo(tipo, argumento, modulos, motivo):
    assert motivo_comando_invalido(tipo, argumento, modulos) == motivo


def test_entregado_sin_ack_en_60_segundos_se_muestra_sin_confirmar():
    assert estado_mostrado("entregado", AHORA - timedelta(seconds=61), AHORA) == "sin_confirmar"
    assert estado_mostrado("entregado", AHORA - timedelta(seconds=60), AHORA) == "entregado"


def test_dispensar_pendiente_o_recien_entregado_bloquea_otro():
    assert bloquea_otro_dispensar("pendiente", None, AHORA)
    assert bloquea_otro_dispensar("entregado", AHORA - timedelta(seconds=10), AHORA)


def test_dispensar_sin_confirmar_o_resuelto_no_bloquea_otro():
    assert not bloquea_otro_dispensar("entregado", AHORA - timedelta(seconds=61), AHORA)
    assert not bloquea_otro_dispensar("confirmado", AHORA, AHORA)
    assert not bloquea_otro_dispensar("expirado", None, AHORA)
