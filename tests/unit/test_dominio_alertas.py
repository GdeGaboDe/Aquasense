from decimal import Decimal as D  # noqa: N817

import pytest

from app.dominio.alertas import (
    Accion,
    evaluar_booleana,
    evaluar_numerica,
    motivo_umbral_invalido,
)

MINIMO, MAXIMO, HISTERESIS = D("24"), D("28"), D("0.5")


def _numerica(valor: str, activa: bool) -> Accion:
    return evaluar_numerica(D(valor), MINIMO, MAXIMO, HISTERESIS, activa)


def test_abre_alerta_cuando_el_valor_supera_el_maximo():
    assert _numerica("28.1", activa=False) == Accion.ABRIR


def test_abre_alerta_cuando_el_valor_baja_del_minimo():
    assert _numerica("23.9", activa=False) == Accion.ABRIR


def test_valor_en_el_limite_no_abre_alerta():
    assert _numerica("28", activa=False) == Accion.NINGUNA


def test_no_abre_otra_si_ya_hay_una_activa():
    assert _numerica("30", activa=True) == Accion.NINGUNA


def test_no_resuelve_dentro_del_rango_pero_fuera_de_la_banda_de_histeresis():
    assert _numerica("27.8", activa=True) == Accion.NINGUNA


def test_resuelve_al_volver_a_la_banda_de_histeresis():
    assert _numerica("27.5", activa=True) == Accion.RESOLVER


def test_umbral_solo_con_maximo_ignora_el_minimo():
    assert evaluar_numerica(D("-5"), None, MAXIMO, HISTERESIS, False) == Accion.NINGUNA
    assert evaluar_numerica(D("29"), None, MAXIMO, HISTERESIS, False) == Accion.ABRIR


@pytest.mark.parametrize(
    ("valor", "activa", "esperado"),
    [
        ("1", False, Accion.ABRIR),
        ("1", True, Accion.NINGUNA),
        ("0", True, Accion.RESOLVER),
        ("0", False, Accion.NINGUNA),
    ],
)
def test_alertas_booleanas(valor, activa, esperado):
    assert evaluar_booleana(D(valor), activa) == esperado


@pytest.mark.parametrize(
    ("minimo", "maximo", "histeresis", "motivo"),
    [
        ("24", "28", "0.5", None),
        (None, "28", "0.5", None),
        ("28", "24", "0", "MINIMO_NO_MENOR_QUE_MAXIMO"),
        ("24", "24", "0", "MINIMO_NO_MENOR_QUE_MAXIMO"),
        ("24", "28", "2", "HISTERESIS_DEMASIADO_GRANDE"),
        ("24", "28", "-1", "HISTERESIS_NEGATIVA"),
        ("-60", "28", "0", "FUERA_DE_RANGO_FISICO"),
    ],
)
def test_valida_umbrales(minimo, maximo, histeresis, motivo):
    resultado = motivo_umbral_invalido(
        D(minimo) if minimo else None,
        D(maximo) if maximo else None,
        D(histeresis),
        D("-55"),
        D("125"),
    )

    assert resultado == motivo
