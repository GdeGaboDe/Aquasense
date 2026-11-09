from decimal import Decimal as D  # noqa: N817

import pytest

from app.dominio.parametros import (
    DefinicionParametro,
    aplica_al_nodo,
    convertir_para_nodo,
    normalizar,
    problemas_entre_parametros,
)

ENTERO = DefinicionParametro("CANTIDAD_CARGAS", "entero", D(1), D(5), None, "1", "servo")
DECIMAL = DefinicionParametro("COEF", "decimal", D("0.80"), D("1.20"), None, "1.00", "tds")
OPCION = DefinicionParametro(
    "MODO_DISPENSA", "opcion", None, None, ("MANUAL", "AUTOMATICO"), "MANUAL", "servo"
)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (3, "3"),
        ("4", "4"),
        (5.0, "5"),
        (0, None),
        (6, None),
        (2.5, None),
        ("x", None),
        (True, None),
    ],
)
def test_normaliza_enteros_dentro_del_rango(valor, esperado):
    assert normalizar(ENTERO, valor) == esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(1, "1"), ("0.95", "0.95"), (1.2, "1.2"), (0.79, None), ("NaN", None), ("inf", None)],
)
def test_normaliza_decimales_dentro_del_rango(valor, esperado):
    assert normalizar(DECIMAL, valor) == esperado


def test_opcion_debe_estar_en_el_catalogo():
    assert normalizar(OPCION, "AUTOMATICO") == "AUTOMATICO"
    assert normalizar(OPCION, "automatico") is None
    assert normalizar(OPCION, 1) is None


def test_parametro_solo_aplica_si_el_nodo_tiene_su_modulo():
    assert aplica_al_nodo(ENTERO, {"servo", "temp"})
    assert not aplica_al_nodo(ENTERO, {"temp"})


def test_parametro_sin_modulo_aplica_a_todos():
    general = DefinicionParametro("INTERVALO_ENVIO_S", "entero", D(5), D(60), None, "10", None)

    assert aplica_al_nodo(general, set())


def test_convierte_al_tipo_que_espera_el_nodo():
    assert convertir_para_nodo(ENTERO, "3") == 3
    assert convertir_para_nodo(DECIMAL, "0.95") == 0.95
    assert convertir_para_nodo(OPCION, "MANUAL") == "MANUAL"


def test_detecta_reglas_entre_parametros():
    problemas = problemas_entre_parametros(
        {"ANGULO_REPOSO_SERVO": "30", "ANGULO_DISPENSA_SERVO": "30", "UMBRAL_LUZ_OSCURIDAD": "10"}
    )

    assert [p.parametro for p in problemas] == ["ANGULO_REPOSO_SERVO"]


def test_regla_entre_parametros_se_omite_si_falta_uno():
    assert problemas_entre_parametros({"TEMP_ENCENDER_CALENTADOR": "29"}) == []
