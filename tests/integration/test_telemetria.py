from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Dosis, Lectura, Nodo, NodoModulo, Sensor, Variable

URL = "/api/v1/device/telemetry"


def _nodo_reportado(mac: str, modulos: list[str], boot: int = 7) -> dict:
    return {
        "mac": mac,
        "firmware": "1.2.0",
        "boot": boot,
        "modulos": modulos,
        "config_version_aplicada": 1,
    }


def _lectura(mac: str, variable: str = "temp_c", valor: float = 25.4, **cambios) -> dict:
    return {
        "mac": mac,
        "variable": variable,
        "valor": valor,
        "edad_ms": 1000,
        "boot": 7,
        "epoch_ms": None,
    } | cambios


def _lote(nodos: list[dict], lecturas: list[dict] | None = None, eventos=None) -> dict:
    return {
        "lote": 1,
        "enviado_epoch_ms": None,
        "nodos": nodos,
        "lecturas": lecturas or [],
        "eventos": eventos or [],
    }


def _enviar(cliente, nodo, lote: dict):
    return cliente.post(URL, json=lote, headers={"X-API-Token": nodo.token})


def _lecturas_guardadas(sesion: Session) -> list[Lectura]:
    sesion.expire_all()
    return list(sesion.scalars(select(Lectura)))


def test_sin_token_responde_401_con_el_formato_de_error(cliente):
    respuesta = cliente.post(URL, json=_lote([]))

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "TOKEN_INVALIDO"


def test_token_invalido_responde_401(cliente):
    respuesta = cliente.post(URL, json=_lote([]), headers={"X-API-Token": "falso"})

    assert respuesta.status_code == 401


def test_autonomo_inactivo_responde_401(cliente, crear_nodo, sesion):
    nodo = crear_nodo()
    sesion.get(Nodo, nodo.id).activo = False
    sesion.commit()

    assert _enviar(cliente, nodo, _lote([])).status_code == 401


def test_json_invalido_responde_422_sin_repetir_los_valores_recibidos(cliente, crear_nodo):
    nodo = crear_nodo()

    respuesta = cliente.post(
        URL,
        json={"lote": "valor-secreto"},
        headers={"X-API-Token": nodo.token},
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["code"] == "DATOS_INVALIDOS"
    assert "valor-secreto" not in respuesta.text


@pytest.mark.parametrize("valor", ["NaN", "Infinity"])
def test_valor_no_finito_responde_422(cliente, crear_nodo, valor):
    nodo = crear_nodo()
    cuerpo = (
        '{"lote":1,"nodos":[],"lecturas":[{"mac":"24:6F:28:00:00:01","variable":"temp_c",'
        f'"valor":{valor},"edad_ms":0,"boot":1}}]}}'
    )

    respuesta = cliente.post(
        URL,
        content=cuerpo,
        headers={"X-API-Token": nodo.token, "Content-Type": "application/json"},
    )

    assert respuesta.status_code == 422


def test_guarda_lectura_con_hora_del_servidor_y_actualiza_el_nodo(cliente, crear_nodo, sesion):
    nodo = crear_nodo()
    antes = datetime.now(UTC)

    respuesta = _enviar(
        cliente, nodo, _lote([_nodo_reportado(nodo.mac, ["temp"])], [_lectura(nodo.mac)])
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"aceptadas": 1, "duplicadas": 0, "rechazadas": []}
    lectura = _lecturas_guardadas(sesion)[0]
    assert lectura.valor == Decimal("25.400")
    assert lectura.origen_hora == "servidor"
    assert lectura.medido_en >= antes - timedelta(milliseconds=1002)
    assert lectura.medido_en <= lectura.recibido_en - timedelta(milliseconds=999)
    guardado = sesion.get(Nodo, nodo.id)
    assert guardado.firmware == "1.2.0"
    assert guardado.boot_actual == 7
    assert guardado.config_version_aplicada == 1
    assert guardado.ultimo_contacto is not None


def test_reenvio_con_la_misma_hora_ntp_cuenta_como_duplicada(cliente, crear_nodo, sesion):
    nodo = crear_nodo()
    epoch = int((datetime.now(UTC) - timedelta(hours=1)).timestamp() * 1000)
    atrasada = _lectura(nodo.mac, boot=6, epoch_ms=epoch)
    nueva = _lectura(nodo.mac, boot=6, epoch_ms=epoch + 10_000)
    reporte = _nodo_reportado(nodo.mac, ["temp"])

    primera = _enviar(cliente, nodo, _lote([reporte], [atrasada]))
    segunda = _enviar(cliente, nodo, _lote([reporte], [atrasada, nueva]))

    assert primera.json()["aceptadas"] == 1
    assert segunda.json() == {"aceptadas": 1, "duplicadas": 1, "rechazadas": []}
    guardadas = _lecturas_guardadas(sesion)
    assert len(guardadas) == 2
    assert {lectura.origen_hora for lectura in guardadas} == {"ntp"}


def test_duplicado_dentro_del_mismo_lote_se_guarda_una_vez(cliente, crear_nodo, sesion):
    nodo = crear_nodo()
    lectura = _lectura(nodo.mac)

    respuesta = _enviar(
        cliente, nodo, _lote([_nodo_reportado(nodo.mac, ["temp"])], [lectura, lectura])
    )

    assert respuesta.json() == {"aceptadas": 1, "duplicadas": 1, "rechazadas": []}
    assert len(_lecturas_guardadas(sesion)) == 1


def test_lectura_de_mac_no_registrada_se_rechaza_sola(cliente, crear_nodo, sesion):
    nodo = crear_nodo()
    lecturas = [_lectura(nodo.mac), _lectura("AA:BB:CC:DD:EE:FF")]

    respuesta = _enviar(cliente, nodo, _lote([_nodo_reportado(nodo.mac, ["temp"])], lecturas))

    assert respuesta.json() == {
        "aceptadas": 1,
        "duplicadas": 0,
        "rechazadas": [{"lista": "lecturas", "indice": 1, "motivo": "MAC_NO_REGISTRADA"}],
    }
    assert len(_lecturas_guardadas(sesion)) == 1


def test_lectura_de_nodo_de_otro_autonomo_se_rechaza_y_no_toca_ese_nodo(
    cliente, crear_nodo, sesion
):
    nodo = crear_nodo()
    ajeno = crear_nodo()
    reportes = [_nodo_reportado(nodo.mac, ["temp"]), _nodo_reportado(ajeno.mac, ["temp"], boot=99)]

    respuesta = _enviar(cliente, nodo, _lote(reportes, [_lectura(ajeno.mac)]))

    assert respuesta.json()["rechazadas"] == [
        {"lista": "lecturas", "indice": 0, "motivo": "NODO_AJENO"}
    ]
    sesion.expire_all()
    assert sesion.get(Nodo, ajeno.id).boot_actual is None


def test_autonomo_reporta_a_su_satelite(cliente, crear_nodo, sesion):
    autonomo = crear_nodo()
    satelite = crear_nodo(padre_id=autonomo.id)
    reportes = [_nodo_reportado(autonomo.mac, ["temp"]), _nodo_reportado(satelite.mac, ["temp"])]

    respuesta = _enviar(cliente, autonomo, _lote(reportes, [_lectura(satelite.mac)]))

    assert respuesta.json()["aceptadas"] == 1
    sesion.expire_all()
    assert sesion.get(Nodo, satelite.id).boot_actual == 7


@pytest.mark.parametrize(
    ("variable", "valor", "motivo"),
    [
        ("inventada", 1, "VARIABLE_DESCONOCIDA"),
        ("temp_c", 500, "FUERA_DE_RANGO_FISICO"),
        ("flotador_bajo", 0.5, "VALOR_NO_BOOLEANO"),
        ("tds_ppm", 100, "VARIABLE_NO_ANUNCIADA"),
    ],
)
def test_rechaza_lecturas_invalidas_individualmente(cliente, crear_nodo, variable, valor, motivo):
    nodo = crear_nodo()
    lecturas = [_lectura(nodo.mac, variable=variable, valor=valor), _lectura(nodo.mac)]
    modulos = ["temp", "flotador"]

    respuesta = _enviar(cliente, nodo, _lote([_nodo_reportado(nodo.mac, modulos)], lecturas))

    cuerpo = respuesta.json()
    assert cuerpo["aceptadas"] == 1
    assert cuerpo["rechazadas"] == [{"lista": "lecturas", "indice": 0, "motivo": motivo}]


def test_autodescubrimiento_de_un_modulo_nuevo_crea_su_sensor(cliente, crear_nodo, sesion):
    nodo = crear_nodo()
    _enviar(cliente, nodo, _lote([_nodo_reportado(nodo.mac, ["temp"])]))

    _enviar(cliente, nodo, _lote([_nodo_reportado(nodo.mac, ["temp", "tolva", "servo"])]))

    sesion.expire_all()
    variables = set(
        sesion.scalars(
            select(Variable.codigo)
            .join(Sensor, Sensor.variable_id == Variable.id)
            .where(Sensor.nodo_id == nodo.id)
        )
    )
    assert variables == {"temp_c", "distancia_tolva_cm", "tolva_vacia"}


def test_guarda_modulos_sin_variables_y_quita_los_retirados(cliente, crear_nodo, sesion):
    nodo = crear_nodo()
    _enviar(cliente, nodo, _lote([_nodo_reportado(nodo.mac, ["temp", "servo", "laser"])]))
    primero = set(sesion.scalars(select(NodoModulo.modulo)))

    _enviar(cliente, nodo, _lote([_nodo_reportado(nodo.mac, ["servo"])]))

    sesion.expire_all()
    sesion.rollback()
    assert primero == {"temp", "servo"}
    assert set(sesion.scalars(select(NodoModulo.modulo))) == {"servo"}
    # El sensor se conserva: su historial sigue siendo válido aunque el módulo se retire.
    assert sesion.scalar(select(Sensor.id).where(Sensor.nodo_id == nodo.id)) is not None


def test_guarda_evento_de_dosis_y_no_lo_duplica_con_la_misma_hora(cliente, crear_nodo, sesion):
    nodo = crear_nodo()
    epoch = int((datetime.now(UTC) - timedelta(hours=1)).timestamp() * 1000)
    evento = {
        "mac": nodo.mac,
        "tipo": "dosis",
        "cargas": 2,
        "origen": "automatico",
        "comando_id": None,
        "edad_ms": 30000,
        "boot": 6,
        "epoch_ms": epoch,
    }
    reporte = _nodo_reportado(nodo.mac, ["servo"])

    primera = _enviar(cliente, nodo, _lote([reporte], eventos=[evento]))
    segunda = _enviar(cliente, nodo, _lote([reporte], eventos=[evento]))

    assert primera.json()["aceptadas"] == 1
    assert segunda.json()["duplicadas"] == 1
    sesion.rollback()
    assert len(sesion.scalars(select(Dosis)).all()) == 1


def test_evento_con_comando_inexistente_se_rechaza_solo(cliente, crear_nodo):
    nodo = crear_nodo()
    evento = {
        "mac": nodo.mac,
        "tipo": "dosis",
        "cargas": 1,
        "origen": "remoto",
        "comando_id": 999,
        "edad_ms": 0,
        "boot": 7,
        "epoch_ms": None,
    }

    respuesta = _enviar(
        cliente, nodo, _lote([_nodo_reportado(nodo.mac, ["servo"])], eventos=[evento])
    )

    assert respuesta.json()["rechazadas"] == [
        {"lista": "eventos", "indice": 0, "motivo": "COMANDO_INVALIDO"}
    ]


def test_mac_en_minusculas_se_normaliza(cliente, crear_nodo, sesion):
    nodo = crear_nodo()

    respuesta = _enviar(
        cliente,
        nodo,
        _lote([_nodo_reportado(nodo.mac.lower(), ["temp"])], [_lectura(nodo.mac.lower())]),
    )

    assert respuesta.json()["aceptadas"] == 1


@pytest.mark.parametrize(
    "headers",
    [{"CF-Connecting-IP": "8.8.8.8"}, {"X-Forwarded-For": "8.8.8.8"}],
)
def test_peticion_que_llega_por_el_tunel_responde_403(cliente, crear_nodo, headers):
    nodo = crear_nodo()

    respuesta = cliente.post(URL, json=_lote([]), headers={"X-API-Token": nodo.token} | headers)

    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["code"] == "SOLO_RED_LOCAL"


def test_peticion_desde_ip_publica_responde_403(crear_cliente, crear_nodo):
    nodo = crear_nodo()

    respuesta = crear_cliente(ip="8.8.8.8").post(
        URL, json=_lote([]), headers={"X-API-Token": nodo.token}
    )

    assert respuesta.status_code == 403
