from datetime import UTC, datetime, timedelta

import pytest

from app.dominio.prediccion import (
    Ciclo,
    ajustar,
    dias_restantes,
    duracion_promedio_dias,
    evaluar,
    momento_de_cruce,
)
from app.dominio.series import intervalo_automatico, promediar

INICIO = datetime(2026, 11, 1, tzinfo=UTC)


def _serie(horas: float, pendiente: float, inicial: float = 150.0, cada_min: int = 30):
    pasos = int(horas * 60 / cada_min)
    return [
        (INICIO + timedelta(minutes=i * cada_min), inicial + pendiente * i * cada_min / 60)
        for i in range(pasos + 1)
    ]


def test_sin_24_horas_de_datos_no_estima():
    assert ajustar(INICIO, _serie(horas=23, pendiente=2, cada_min=10)) is None


def test_con_menos_de_50_muestras_no_estima():
    assert ajustar(INICIO, _serie(horas=48, pendiente=2, cada_min=60)) is None


def test_ajusta_la_recta_de_una_serie_lineal():
    ajuste = ajustar(INICIO, _serie(horas=48, pendiente=2))

    assert ajuste is not None
    assert ajuste.pendiente_ppm_h == pytest.approx(2)
    assert ajuste.intercepto_ppm == pytest.approx(150)
    assert ajuste.r2 == pytest.approx(1)
    assert ajuste.n_muestras == 97


def test_cruce_correcto_con_el_umbral():
    ajuste = ajustar(INICIO, _serie(horas=48, pendiente=2))

    cruce = momento_de_cruce(INICIO, ajuste, limite=390)

    assert cruce == pytest.approx(INICIO + timedelta(hours=120), abs=timedelta(seconds=1))


def test_pendiente_plana_o_negativa_no_tiene_cruce():
    plano = ajustar(INICIO, _serie(horas=48, pendiente=0))
    bajando = ajustar(INICIO, _serie(horas=48, pendiente=-1))

    assert momento_de_cruce(INICIO, plano, 400) is None
    assert momento_de_cruce(INICIO, bajando, 400) is None


def test_serie_constante_no_falla_al_calcular_r2():
    assert ajustar(INICIO, _serie(horas=48, pendiente=0)).r2 is None


def test_dias_restantes_no_son_negativos_si_ya_se_supero_el_limite():
    cruce = INICIO + timedelta(days=2)

    assert dias_restantes(cruce, INICIO) == pytest.approx(2)
    assert dias_restantes(cruce, INICIO + timedelta(days=3)) == 0


def test_baseline_es_la_duracion_promedio_de_los_ciclos_completos():
    cambios = [INICIO, INICIO + timedelta(days=6), INICIO + timedelta(days=14)]

    assert duracion_promedio_dias(cambios) == pytest.approx(7)


def test_sin_ciclos_completos_no_hay_baseline():
    assert duracion_promedio_dias([INICIO]) is None


def test_evaluacion_usa_solo_ciclos_anteriores_para_el_baseline():
    anterior = Ciclo(INICIO - timedelta(days=4), INICIO, [])
    # Sube 1 ppm cada 30 minutos: 2 ppm/h durante 10 días.
    lecturas = [(INICIO + timedelta(minutes=30 * i), 150 + i) for i in range(481)]
    evaluado = Ciclo(INICIO, INICIO + timedelta(days=5), lecturas)

    resultado = evaluar([evaluado, anterior], limite=390)

    assert resultado is not None
    # El modelo predice el cambio a las 120 h, justo cuando ocurrió.
    assert resultado.mae_modelo_dias == pytest.approx(0, abs=0.01)
    # El baseline (4 días, del ciclo anterior) se equivoca por 1 día.
    assert resultado.mae_baseline_dias == pytest.approx(1)
    # Cortes a las 48, 72 y 96 h; el de 24 h no junta las 50 muestras mínimas.
    assert resultado.predicciones_evaluadas == 3


def test_evaluacion_no_usa_lecturas_posteriores_al_corte():
    # Plano el primer día y luego sube: con solo el primer día no hay pendiente que extrapolar.
    lecturas = [(INICIO + timedelta(minutes=30 * i), 150.0) for i in range(49)] + [
        (INICIO + timedelta(hours=24, minutes=30 * i), 150 + i) for i in range(1, 49)
    ]
    evaluado = Ciclo(INICIO, INICIO + timedelta(days=2), lecturas)

    assert evaluar([evaluado], limite=400) is None


def test_agrega_promedios_por_intervalo_y_omite_huecos():
    lecturas = [
        (INICIO + timedelta(seconds=10), 10.0),
        (INICIO + timedelta(seconds=50), 20.0),
        (INICIO + timedelta(minutes=3, seconds=5), 40.0),
    ]

    puntos = promediar(lecturas, INICIO, timedelta(minutes=1))

    assert puntos == [(INICIO, 15.0, 2), (INICIO + timedelta(minutes=3), 40.0, 1)]


@pytest.mark.parametrize(
    ("horas", "esperado"),
    [(6, "1m"), (33, "1m"), (34, "5m"), (24 * 6, "5m"), (24 * 7, "1h")],
)
def test_intervalo_automatico_respeta_el_maximo_de_puntos(horas, esperado):
    assert intervalo_automatico(INICIO, INICIO + timedelta(hours=horas)) == esperado


def test_pendiente_casi_cero_por_redondeo_no_inventa_un_cruce_lejano():
    ajuste = ajustar(INICIO, _serie(horas=48, pendiente=1e-9))

    assert momento_de_cruce(INICIO, ajuste, 400) is None
