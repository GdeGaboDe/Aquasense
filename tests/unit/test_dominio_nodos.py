from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.dominio.conexion import esta_sin_conexion
from app.dominio.lecturas import motivo_de_rechazo
from app.dominio.modulos import modulos_conocidos, variables_de_modulos

AHORA = datetime(2026, 11, 20, 15, 0, 0, tzinfo=UTC)


def test_modulos_sin_variables_no_generan_sensores():
    assert variables_de_modulos(["servo", "rtc"]) == set()


def test_un_modulo_puede_reportar_varias_variables():
    assert variables_de_modulos(["tolva"]) == {"distancia_tolva_cm", "tolva_vacia"}


def test_modulo_desconocido_se_descarta_sin_fallar():
    assert modulos_conocidos(["temp", "laser"]) == {"temp"}
    assert variables_de_modulos(["laser"]) == set()


def test_nodo_que_nunca_reporto_esta_sin_conexion():
    assert esta_sin_conexion(None, AHORA) is True


def test_nodo_en_el_limite_de_30_segundos_sigue_conectado():
    assert esta_sin_conexion(AHORA - timedelta(seconds=30), AHORA) is False


def test_nodo_pasado_el_limite_de_30_segundos_esta_sin_conexion():
    assert esta_sin_conexion(AHORA - timedelta(seconds=31), AHORA) is True


@pytest.mark.parametrize(
    ("valor", "tipo", "esperado"),
    [
        ("25.4", "numero", None),
        ("0", "numero", None),
        ("100", "numero", None),
        ("-0.001", "numero", "FUERA_DE_RANGO_FISICO"),
        ("100.001", "numero", "FUERA_DE_RANGO_FISICO"),
        ("1", "booleano", None),
        ("0.5", "booleano", "VALOR_NO_BOOLEANO"),
    ],
)
def test_valida_el_valor_contra_el_catalogo(valor, tipo, esperado):
    assert motivo_de_rechazo(Decimal(valor), tipo, Decimal(0), Decimal(100)) == esperado


def test_variable_sin_limites_acepta_cualquier_numero():
    assert motivo_de_rechazo(Decimal("-9999"), "numero", None, None) is None
