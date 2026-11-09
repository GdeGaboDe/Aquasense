from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import CambioAgua, Lectura, OrigenHora, Prediccion, Sensor, Variable


def _sensor(sesion: Session, nodo_id: int, codigo: str) -> int:
    variable_id = sesion.scalar(select(Variable.id).where(Variable.codigo == codigo))
    sensor = Sensor(
        nodo_id=nodo_id,
        variable_id=variable_id,
        detectado_en=datetime.now(UTC),
        ultimo_visto=datetime.now(UTC),
    )
    sesion.add(sensor)
    sesion.commit()
    return sensor.id


def _lecturas(sesion, sensor_id, inicio, horas, por_hora, valor, origen=OrigenHora.SERVIDOR):
    """Inserta lecturas cada 1/por_hora horas; `valor` recibe las horas transcurridas."""
    for i in range(int(horas * por_hora)):
        momento = inicio + timedelta(hours=i / por_hora)
        sesion.add(
            Lectura(
                sensor_id=sensor_id,
                medido_en=momento,
                valor=Decimal(str(round(valor(i / por_hora), 3))),
                recibido_en=momento,
                origen_hora=origen,
            )
        )
    sesion.commit()


def _cambio(sesion, tanque_id, usuario_id, momento):
    sesion.add(
        CambioAgua(
            tanque_id=tanque_id, realizado_en=momento, porcentaje=100, registrado_por=usuario_id
        )
    )
    sesion.commit()


# --- Series para gráficas ---


def test_serie_agrega_promedios_por_intervalo(cliente_con_sesion, crear_nodo, sesion):
    nodo = crear_nodo()
    sensor_id = _sensor(sesion, nodo.id, "temp_c")
    inicio = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(hours=3)
    _lecturas(sesion, sensor_id, inicio, horas=2, por_hora=60, valor=lambda h: 20 + (h >= 1))

    respuesta = cliente_con_sesion.get(
        f"/api/v1/tanques/{nodo.tanque_id}/lecturas",
        params={"variable": "temp_c", "desde": inicio.isoformat(), "intervalo": "1h"},
    )

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["intervalo"] == "1h"
    assert [(p["valor"], p["muestras"]) for p in cuerpo["puntos"]] == [(20.0, 60), (21.0, 60)]


def test_serie_excluye_hora_desconocida_salvo_que_se_pida(cliente_con_sesion, crear_nodo, sesion):
    nodo = crear_nodo()
    sensor_id = _sensor(sesion, nodo.id, "temp_c")
    inicio = datetime.now(UTC) - timedelta(hours=2)
    _lecturas(sesion, sensor_id, inicio, 1, 6, lambda h: 25, origen=OrigenHora.DESCONOCIDA)
    url = f"/api/v1/tanques/{nodo.tanque_id}/lecturas"

    por_defecto = cliente_con_sesion.get(url, params={"variable": "temp_c"}).json()
    con_todas = cliente_con_sesion.get(
        url, params={"variable": "temp_c", "incluir_desconocidas": "true"}
    ).json()

    assert por_defecto["puntos"] == []
    assert sum(p["muestras"] for p in con_todas["puntos"]) == 6


def test_serie_sin_sensor_devuelve_lista_vacia(cliente_con_sesion, crear_nodo):
    nodo = crear_nodo()

    respuesta = cliente_con_sesion.get(
        f"/api/v1/tanques/{nodo.tanque_id}/lecturas", params={"variable": "tds_ppm"}
    )

    assert respuesta.json()["puntos"] == []
    assert respuesta.json()["intervalo"] == "1m"


@pytest.mark.parametrize(
    ("params", "codigo"),
    [
        (
            {
                "variable": "temp_c",
                "desde": "2026-11-10T00:00:00Z",
                "hasta": "2026-11-01T00:00:00Z",
            },
            "RANGO_INVALIDO",
        ),
        (
            {
                "variable": "temp_c",
                "desde": "2026-09-01T00:00:00Z",
                "hasta": "2026-11-01T00:00:00Z",
            },
            "RANGO_DEMASIADO_GRANDE",
        ),
        (
            {
                "variable": "temp_c",
                "desde": "2026-10-25T00:00:00Z",
                "hasta": "2026-11-01T00:00:00Z",
                "intervalo": "1m",
            },
            "DEMASIADOS_PUNTOS",
        ),
    ],
)
def test_serie_rechaza_rangos_invalidos(cliente_con_sesion, crear_nodo, params, codigo):
    nodo = crear_nodo()

    respuesta = cliente_con_sesion.get(f"/api/v1/tanques/{nodo.tanque_id}/lecturas", params=params)

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["code"] == codigo


def test_serie_exige_fechas_con_zona_horaria(cliente_con_sesion, crear_nodo):
    nodo = crear_nodo()

    respuesta = cliente_con_sesion.get(
        f"/api/v1/tanques/{nodo.tanque_id}/lecturas",
        params={"variable": "temp_c", "desde": "2026-11-01T00:00:00"},
    )

    assert respuesta.status_code == 422


def test_serie_de_variable_inexistente_responde_404(cliente_con_sesion, crear_nodo):
    nodo = crear_nodo()

    respuesta = cliente_con_sesion.get(
        f"/api/v1/tanques/{nodo.tanque_id}/lecturas", params={"variable": "inventada"}
    )

    assert respuesta.status_code == 404


# --- Cambios de agua ---


def test_registrar_cambio_de_agua_y_listarlo(cliente_con_sesion, crear_nodo, usuario, sesion):
    nodo = crear_nodo()
    _cambio(sesion, nodo.tanque_id, usuario.id, datetime.now(UTC) - timedelta(days=3))
    url = f"/api/v1/tanques/{nodo.tanque_id}/cambios-agua"

    creado = cliente_con_sesion.post(url, json={"porcentaje": 30})
    listado = cliente_con_sesion.get(url).json()

    assert creado.status_code == 201
    assert creado.json()["porcentaje"] == 30
    assert listado["total"] == 2
    assert listado["elementos"][0]["id"] == creado.json()["id"]


@pytest.mark.parametrize(
    ("cuerpo", "codigo_http"),
    [
        ({"porcentaje": 0}, 422),
        ({"porcentaje": 101}, 422),
        ({"porcentaje": 50, "realizado_en": "2026-11-01T00:00:00"}, 422),
    ],
)
def test_cambio_de_agua_invalido(cliente_con_sesion, crear_nodo, cuerpo, codigo_http):
    nodo = crear_nodo()

    respuesta = cliente_con_sesion.post(
        f"/api/v1/tanques/{nodo.tanque_id}/cambios-agua", json=cuerpo
    )

    assert respuesta.status_code == codigo_http


def test_cambio_de_agua_en_el_futuro_o_antes_del_ultimo_se_rechaza(
    cliente_con_sesion, crear_nodo, usuario, sesion
):
    nodo = crear_nodo()
    ultimo = datetime.now(UTC) - timedelta(days=1)
    _cambio(sesion, nodo.tanque_id, usuario.id, ultimo)
    url = f"/api/v1/tanques/{nodo.tanque_id}/cambios-agua"

    futuro = cliente_con_sesion.post(
        url,
        json={
            "porcentaje": 50,
            "realizado_en": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    anterior = cliente_con_sesion.post(
        url, json={"porcentaje": 50, "realizado_en": (ultimo - timedelta(hours=1)).isoformat()}
    )

    assert futuro.json()["error"]["code"] == "FECHA_FUTURA"
    assert anterior.json()["error"]["code"] == "FECHA_ANTERIOR_AL_ULTIMO_CAMBIO"


# --- Predicción ---


def _fijar_limite(cliente, tanque_id, maximo):
    respuesta = cliente.put(
        f"/api/v1/tanques/{tanque_id}/umbrales",
        json={"umbrales": [{"variable": "tds_ppm", "maximo": maximo}]},
    )
    assert respuesta.status_code == 200, respuesta.text


def test_prediccion_no_confiable_sin_24_horas_de_datos(
    cliente_con_sesion, crear_nodo, usuario, sesion
):
    nodo = crear_nodo()
    ahora = datetime.now(UTC)
    _cambio(sesion, nodo.tanque_id, usuario.id, ahora - timedelta(hours=10))
    sensor_id = _sensor(sesion, nodo.id, "tds_ppm")
    _lecturas(sesion, sensor_id, ahora - timedelta(hours=10), 10, 12, lambda h: 150 + 2 * h)
    _fijar_limite(cliente_con_sesion, nodo.tanque_id, 400)

    respuesta = cliente_con_sesion.get(f"/api/v1/tanques/{nodo.tanque_id}/prediccion").json()

    assert respuesta["estado"] == "no_confiable"
    assert respuesta["motivo"] == "DATOS_INSUFICIENTES"
    assert respuesta["dias_restantes"] is None


def test_prediccion_estima_el_cruce_con_el_umbral_y_la_guarda(
    cliente_con_sesion, crear_nodo, usuario, sesion
):
    nodo = crear_nodo()
    inicio = datetime.now(UTC) - timedelta(hours=48)
    _cambio(sesion, nodo.tanque_id, usuario.id, inicio)
    sensor_id = _sensor(sesion, nodo.id, "tds_ppm")
    _lecturas(sesion, sensor_id, inicio, 48, 4, lambda h: 150 + 2 * h)  # 2 ppm/h
    _fijar_limite(cliente_con_sesion, nodo.tanque_id, 390)  # cruce a las 120 h

    primera = cliente_con_sesion.get(f"/api/v1/tanques/{nodo.tanque_id}/prediccion").json()
    cliente_con_sesion.get(f"/api/v1/tanques/{nodo.tanque_id}/prediccion")

    assert primera["estado"] == "confiable"
    assert primera["dias_restantes"] == pytest.approx(3, abs=0.02)
    assert primera["pendiente_ppm_por_dia"] == pytest.approx(48, abs=0.1)
    assert primera["n_muestras"] == 192
    # Como máximo una fila por hora y por ciclo.
    assert len(sesion.scalars(select(Prediccion)).all()) == 1


def test_prediccion_con_pendiente_negativa_no_inventa_dias(
    cliente_con_sesion, crear_nodo, usuario, sesion
):
    nodo = crear_nodo()
    inicio = datetime.now(UTC) - timedelta(hours=30)
    _cambio(sesion, nodo.tanque_id, usuario.id, inicio)
    sensor_id = _sensor(sesion, nodo.id, "tds_ppm")
    _lecturas(sesion, sensor_id, inicio, 30, 4, lambda h: 300 - h)
    _fijar_limite(cliente_con_sesion, nodo.tanque_id, 400)

    respuesta = cliente_con_sesion.get(f"/api/v1/tanques/{nodo.tanque_id}/prediccion").json()

    assert respuesta["motivo"] == "PENDIENTE_NO_POSITIVA"
    assert respuesta["dias_restantes"] is None
    assert sesion.scalars(select(Prediccion)).all() == []


def test_prediccion_sin_umbral_de_tds_lo_indica(cliente_con_sesion, crear_nodo, usuario, sesion):
    nodo = crear_nodo()
    _cambio(sesion, nodo.tanque_id, usuario.id, datetime.now(UTC) - timedelta(days=1))
    _sensor(sesion, nodo.id, "tds_ppm")

    respuesta = cliente_con_sesion.get(f"/api/v1/tanques/{nodo.tanque_id}/prediccion").json()

    assert respuesta["motivo"] == "SIN_UMBRAL_TDS"


def test_prediccion_muestra_baseline_y_evaluacion_con_ciclos_anteriores(
    cliente_con_sesion, crear_nodo, usuario, sesion
):
    nodo = crear_nodo()
    ahora = datetime.now(UTC)
    inicio_anterior = ahora - timedelta(days=9)
    inicio_actual = ahora - timedelta(days=4)
    _cambio(sesion, nodo.tanque_id, usuario.id, ahora - timedelta(days=13))
    _cambio(sesion, nodo.tanque_id, usuario.id, inicio_anterior)
    _cambio(sesion, nodo.tanque_id, usuario.id, inicio_actual)
    sensor_id = _sensor(sesion, nodo.id, "tds_ppm")
    _lecturas(sesion, sensor_id, inicio_anterior, 24 * 5, 2, lambda h: 150 + 2 * h)
    _fijar_limite(cliente_con_sesion, nodo.tanque_id, 390)

    respuesta = cliente_con_sesion.get(f"/api/v1/tanques/{nodo.tanque_id}/prediccion").json()

    assert respuesta["baseline_dias"] == pytest.approx(4.5)
    assert respuesta["baseline_dias_restantes"] == pytest.approx(0.5, abs=0.01)
    # El ciclo actual todavía no tiene lecturas: sin estimación, pero con baseline y evaluación.
    assert respuesta["motivo"] == "DATOS_INSUFICIENTES"
    evaluacion = respuesta["evaluacion"]
    assert evaluacion["mae_modelo_dias"] == pytest.approx(0, abs=0.02)
    assert evaluacion["mae_baseline_dias"] == pytest.approx(1)


def test_prediccion_de_tanque_inexistente_responde_404(cliente_con_sesion):
    assert cliente_con_sesion.get("/api/v1/tanques/999/prediccion").status_code == 404


def test_rutas_de_analisis_exigen_sesion(cliente, crear_nodo):
    nodo = crear_nodo()

    for ruta in ("lecturas?variable=temp_c", "cambios-agua", "prediccion"):
        assert cliente.get(f"/api/v1/tanques/{nodo.tanque_id}/{ruta}").status_code == 401
