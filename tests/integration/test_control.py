from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Alerta, Comando, Dosis, Nodo, TipoAlerta

TELEMETRIA = "/api/v1/device/telemetry"
CONFIG = "/api/v1/device/config"
ACK = "/api/v1/device/ack"
COMANDOS = "/api/v1/comandos"
ALERTAS = "/api/v1/alertas"


def _token(nodo) -> dict:
    return {"X-API-Token": nodo.token}


def _reportar(cliente, nodo, modulos, lecturas=(), eventos=(), boot=7) -> dict:
    respuesta = cliente.post(
        TELEMETRIA,
        json={
            "lote": 1,
            "nodos": [{"mac": nodo.mac, "boot": boot, "modulos": list(modulos)}],
            "lecturas": [
                {"mac": nodo.mac, "boot": boot, "edad_ms": edad, "variable": var, "valor": valor}
                for var, valor, edad in lecturas
            ],
            "eventos": list(eventos),
        },
        headers=_token(nodo),
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _dispensar(cliente, nodo_id, cargas=2):
    return cliente.post(
        COMANDOS, json={"nodo_id": nodo_id, "tipo": "DISPENSAR", "argumento": cargas}
    )


def _alertas_activas(sesion: Session) -> list[tuple[str, int | None]]:
    # Cierra la transacción: con REPEATABLE READ, MySQL seguiría mostrando la foto anterior.
    sesion.rollback()
    consulta = (
        select(TipoAlerta.codigo, Alerta.variable_id)
        .join(TipoAlerta, TipoAlerta.id == Alerta.tipo_alerta_id)
        .where(Alerta.resuelta_en.is_(None))
    )
    return [tuple(fila) for fila in sesion.execute(consulta)]


@pytest.fixture
def nodo_con_servo(cliente_con_sesion, crear_nodo):
    nodo = crear_nodo()
    _reportar(cliente_con_sesion, nodo, ["temp", "servo", "alarma", "flotador", "tolva"])
    return nodo


# --- Comandos, configuración y ACK ---


def test_dispensar_viaja_al_nodo_y_queda_confirmado(cliente_con_sesion, nodo_con_servo):
    creado = _dispensar(cliente_con_sesion, nodo_con_servo.id)

    config = cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))
    ack = cliente_con_sesion.post(
        ACK,
        json={"comando_id": creado.json()["id"], "resultado": "confirmado"},
        headers=_token(nodo_con_servo),
    )
    estado = cliente_con_sesion.get(COMANDOS, params={"nodo_id": nodo_con_servo.id})

    assert creado.status_code == 201
    assert creado.json()["estado"] == "pendiente"
    assert config.json()["comandos"] == [
        {"id": creado.json()["id"], "mac": nodo_con_servo.mac, "tipo": "DISPENSAR", "argumento": 2}
    ]
    assert ack.json() == {"comando_id": creado.json()["id"], "estado": "confirmado"}
    assert estado.json()["elementos"][0]["estado"] == "confirmado"


def test_un_comando_entregado_no_se_vuelve_a_entregar(cliente_con_sesion, nodo_con_servo):
    _dispensar(cliente_con_sesion, nodo_con_servo.id)

    primera = cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))
    segunda = cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))

    assert len(primera.json()["comandos"]) == 1
    assert segunda.json()["comandos"] == []


def test_segundo_dispensar_activo_responde_409(cliente_con_sesion, nodo_con_servo):
    _dispensar(cliente_con_sesion, nodo_con_servo.id)

    respuesta = _dispensar(cliente_con_sesion, nodo_con_servo.id)

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "DISPENSAR_EN_CURSO"


def test_otro_tipo_de_comando_no_choca_con_un_dispensar_activo(cliente_con_sesion, nodo_con_servo):
    _dispensar(cliente_con_sesion, nodo_con_servo.id)

    respuesta = cliente_con_sesion.post(
        COMANDOS, json={"nodo_id": nodo_con_servo.id, "tipo": "SILENCIAR_ALARMA", "argumento": 10}
    )

    assert respuesta.status_code == 201


def test_dispensar_sin_confirmar_ya_no_bloquea_uno_nuevo(
    cliente_con_sesion, nodo_con_servo, sesion
):
    creado = _dispensar(cliente_con_sesion, nodo_con_servo.id).json()
    cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))
    comando = sesion.get(Comando, creado["id"])
    comando.entregado_en = datetime.now(UTC) - timedelta(seconds=61)
    sesion.commit()

    listado = cliente_con_sesion.get(COMANDOS, params={"nodo_id": nodo_con_servo.id})
    nuevo = _dispensar(cliente_con_sesion, nodo_con_servo.id)

    assert listado.json()["elementos"][0]["estado"] == "sin_confirmar"
    assert nuevo.status_code == 201


def test_comando_sin_el_modulo_requerido_responde_400(cliente_con_sesion, crear_nodo):
    nodo = crear_nodo()
    _reportar(cliente_con_sesion, nodo, ["temp"])

    respuesta = _dispensar(cliente_con_sesion, nodo.id)

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["code"] == "MODULO_NO_DISPONIBLE"


def test_argumento_fuera_de_rango_responde_422(cliente_con_sesion, nodo_con_servo):
    assert _dispensar(cliente_con_sesion, nodo_con_servo.id, cargas=6).status_code == 422


def test_comandos_exigen_sesion(cliente, crear_nodo):
    assert cliente.post(COMANDOS, json={}).status_code == 401
    assert cliente.get(COMANDOS).status_code == 401


def test_pendiente_no_entregado_expira_y_genera_alerta(cliente_con_sesion, nodo_con_servo, sesion):
    creado = _dispensar(cliente_con_sesion, nodo_con_servo.id).json()
    comando = sesion.get(Comando, creado["id"])
    comando.expira_en = datetime.now(UTC) - timedelta(seconds=1)
    sesion.commit()

    config = cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))

    assert config.json()["comandos"] == []
    sesion.expire_all()
    assert sesion.get(Comando, creado["id"]).estado == "expirado"
    assert _alertas_activas(sesion) == [("COMANDO_FALLIDO", None)]


def test_ack_fallido_abre_alerta_y_un_confirmado_posterior_la_resuelve(
    cliente_con_sesion, nodo_con_servo, sesion
):
    primero = _dispensar(cliente_con_sesion, nodo_con_servo.id).json()
    cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))
    cliente_con_sesion.post(
        ACK,
        json={"comando_id": primero["id"], "resultado": "fallido", "detalle": "Servo trabado"},
        headers=_token(nodo_con_servo),
    )
    con_alerta = _alertas_activas(sesion)

    segundo = _dispensar(cliente_con_sesion, nodo_con_servo.id).json()
    cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))
    cliente_con_sesion.post(
        ACK,
        json={"comando_id": segundo["id"], "resultado": "confirmado"},
        headers=_token(nodo_con_servo),
    )

    assert con_alerta == [("COMANDO_FALLIDO", None)]
    assert _alertas_activas(sesion) == []
    assert sesion.get(Comando, primero["id"]).detalle == "Servo trabado"


def test_repetir_el_mismo_ack_no_cambia_nada(cliente_con_sesion, nodo_con_servo, sesion):
    creado = _dispensar(cliente_con_sesion, nodo_con_servo.id).json()
    cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))
    cuerpo = {"comando_id": creado["id"], "resultado": "confirmado"}
    cliente_con_sesion.post(ACK, json=cuerpo, headers=_token(nodo_con_servo))
    resuelto_en = sesion.get(Comando, creado["id"]).resuelto_en

    repetido = cliente_con_sesion.post(ACK, json=cuerpo, headers=_token(nodo_con_servo))

    sesion.expire_all()
    assert repetido.status_code == 200
    assert sesion.get(Comando, creado["id"]).resuelto_en == resuelto_en


def test_ack_contradictorio_responde_409(cliente_con_sesion, nodo_con_servo):
    creado = _dispensar(cliente_con_sesion, nodo_con_servo.id).json()
    cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))
    cliente_con_sesion.post(
        ACK,
        json={"comando_id": creado["id"], "resultado": "confirmado"},
        headers=_token(nodo_con_servo),
    )

    respuesta = cliente_con_sesion.post(
        ACK,
        json={"comando_id": creado["id"], "resultado": "fallido"},
        headers=_token(nodo_con_servo),
    )

    assert respuesta.status_code == 409


def test_ack_de_comando_de_otro_autonomo_responde_403(
    cliente_con_sesion, nodo_con_servo, crear_nodo
):
    ajeno = crear_nodo()
    creado = _dispensar(cliente_con_sesion, nodo_con_servo.id).json()

    respuesta = cliente_con_sesion.post(
        ACK, json={"comando_id": creado["id"], "resultado": "confirmado"}, headers=_token(ajeno)
    )

    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["code"] == "COMANDO_AJENO"


def test_ack_de_comando_inexistente_responde_404(cliente_con_sesion, nodo_con_servo):
    respuesta = cliente_con_sesion.post(
        ACK, json={"comando_id": 9999, "resultado": "confirmado"}, headers=_token(nodo_con_servo)
    )

    assert respuesta.status_code == 404


def test_config_sin_token_responde_401_y_por_tunel_403(cliente, crear_nodo):
    nodo = crear_nodo()

    assert cliente.get(CONFIG).status_code == 401
    assert (
        cliente.get(CONFIG, headers=_token(nodo) | {"CF-Connecting-IP": "8.8.8.8"}).status_code
        == 403
    )


def test_comando_a_un_satelite_lo_entrega_su_autonomo(cliente_con_sesion, crear_nodo):
    autonomo = crear_nodo()
    satelite = crear_nodo(padre_id=autonomo.id)
    cliente_con_sesion.post(
        TELEMETRIA,
        json={
            "lote": 1,
            "nodos": [
                {"mac": autonomo.mac, "boot": 1, "modulos": ["temp"]},
                {"mac": satelite.mac, "boot": 1, "modulos": ["servo"]},
            ],
        },
        headers=_token(autonomo),
    )
    _dispensar(cliente_con_sesion, satelite.id)

    config = cliente_con_sesion.get(CONFIG, headers=_token(autonomo)).json()

    assert [c["mac"] for c in config["comandos"]] == [satelite.mac]
    assert {n["mac"] for n in config["nodos"]} == {autonomo.mac, satelite.mac}


def test_dosis_confirmada_se_liga_a_su_comando_y_aparece_en_la_bitacora(
    cliente_con_sesion, nodo_con_servo, sesion
):
    creado = _dispensar(cliente_con_sesion, nodo_con_servo.id).json()
    cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo))
    evento = {
        "mac": nodo_con_servo.mac,
        "tipo": "dosis",
        "cargas": 2,
        "origen": "remoto",
        "comando_id": creado["id"],
        "edad_ms": 100,
        "boot": 7,
    }
    _reportar(cliente_con_sesion, nodo_con_servo, ["servo"], eventos=[evento])

    bitacora = cliente_con_sesion.get(f"/api/v1/tanques/{nodo_con_servo.tanque_id}/dosis").json()

    assert sesion.scalar(select(Dosis.comando_id)) == creado["id"]
    assert bitacora["total"] == 1
    assert bitacora["elementos"][0]["origen"] == "remoto"


# --- Configuración y parámetros ---


def test_config_solo_incluye_parametros_de_los_modulos_del_nodo(cliente_con_sesion, crear_nodo):
    nodo = crear_nodo()
    _reportar(cliente_con_sesion, nodo, ["servo"])

    config = cliente_con_sesion.get(CONFIG, headers=_token(nodo)).json()

    parametros = config["nodos"][0]["parametros"]
    assert parametros["MODO_DISPENSA"] == "MANUAL"
    assert parametros["CANTIDAD_CARGAS"] == 1
    assert parametros["VOLTAJE_REFERENCIA_ADC"] == 3.3
    assert "FRECUENCIA_ALARMA_BUZZER" not in parametros
    assert abs(config["servidor_epoch_ms"] - datetime.now(UTC).timestamp() * 1000) < 5000


def test_cambiar_parametros_sube_config_version_y_llega_al_nodo(
    cliente_con_sesion, nodo_con_servo, sesion
):
    url = f"/api/v1/nodos/{nodo_con_servo.id}/parametros"

    respuesta = cliente_con_sesion.put(
        url, json={"valores": {"MODO_DISPENSA": "AUTOMATICO", "CANTIDAD_CARGAS": 3}}
    )
    config = cliente_con_sesion.get(CONFIG, headers=_token(nodo_con_servo)).json()

    assert respuesta.status_code == 200
    assert respuesta.json()["config_version"] == 2
    assert respuesta.json()["pendiente_de_aplicar"] is True
    assert config["nodos"][0]["config_version"] == 2
    assert config["nodos"][0]["parametros"]["CANTIDAD_CARGAS"] == 3


def test_guardar_el_mismo_valor_no_sube_config_version(cliente_con_sesion, nodo_con_servo):
    url = f"/api/v1/nodos/{nodo_con_servo.id}/parametros"
    cliente_con_sesion.put(url, json={"valores": {"CANTIDAD_CARGAS": 3}})

    respuesta = cliente_con_sesion.put(url, json={"valores": {"CANTIDAD_CARGAS": 3}})

    assert respuesta.json()["config_version"] == 2


def test_parametro_invalido_no_guarda_nada_ni_sube_version(
    cliente_con_sesion, nodo_con_servo, sesion
):
    url = f"/api/v1/nodos/{nodo_con_servo.id}/parametros"

    respuesta = cliente_con_sesion.put(
        url, json={"valores": {"MODO_DISPENSA": "AUTOMATICO", "CANTIDAD_CARGAS": 9}}
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["details"] == [
        {"parametro": "CANTIDAD_CARGAS", "motivo": "VALOR_INVALIDO"}
    ]
    sesion.expire_all()
    assert sesion.get(Nodo, nodo_con_servo.id).config_version == 1


def test_parametro_de_un_modulo_que_el_nodo_no_tiene_se_rechaza(cliente_con_sesion, nodo_con_servo):
    respuesta = cliente_con_sesion.put(
        f"/api/v1/nodos/{nodo_con_servo.id}/parametros",
        json={"valores": {"COEF_CALIBRACION_TDS": 1.0, "INVENTADO": 1}},
    )

    assert respuesta.json()["error"]["details"] == [
        {"parametro": "COEF_CALIBRACION_TDS", "motivo": "MODULO_NO_DISPONIBLE"},
        {"parametro": "INVENTADO", "motivo": "PARAMETRO_DESCONOCIDO"},
    ]


def test_regla_entre_parametros_se_valida_con_los_valores_ya_guardados(
    cliente_con_sesion, nodo_con_servo
):
    respuesta = cliente_con_sesion.put(
        f"/api/v1/nodos/{nodo_con_servo.id}/parametros",
        json={"valores": {"ANGULO_DISPENSA_SERVO": 45, "ANGULO_REPOSO_SERVO": 30}},
    )
    valido = cliente_con_sesion.put(
        f"/api/v1/nodos/{nodo_con_servo.id}/parametros",
        json={"valores": {"ANGULO_DISPENSA_SERVO": 45}},
    )

    assert respuesta.status_code == 200
    assert valido.status_code == 200


def test_regla_entre_parametros_rota_responde_422(cliente_con_sesion, crear_nodo):
    nodo = crear_nodo()
    _reportar(cliente_con_sesion, nodo, ["luz"])

    respuesta = cliente_con_sesion.put(
        f"/api/v1/nodos/{nodo.id}/parametros",
        json={"valores": {"UMBRAL_LUZ_OSCURIDAD": 1500, "UMBRAL_LUZ_MODERADA": 1501}},
    )
    rota = cliente_con_sesion.put(
        f"/api/v1/nodos/{nodo.id}/parametros",
        json={"valores": {"UMBRAL_LUZ_OSCURIDAD": 1500, "UMBRAL_LUZ_MODERADA": 1500}},
    )

    assert respuesta.status_code == 200
    assert rota.status_code == 422


def test_el_nodo_reporta_la_version_aplicada_y_deja_de_estar_pendiente(
    cliente_con_sesion, nodo_con_servo
):
    url = f"/api/v1/nodos/{nodo_con_servo.id}/parametros"
    cliente_con_sesion.put(url, json={"valores": {"CANTIDAD_CARGAS": 4}})
    cliente_con_sesion.post(
        TELEMETRIA,
        json={
            "lote": 2,
            "nodos": [
                {
                    "mac": nodo_con_servo.mac,
                    "boot": 7,
                    "modulos": ["servo"],
                    "config_version_aplicada": 2,
                }
            ],
        },
        headers=_token(nodo_con_servo),
    )

    assert cliente_con_sesion.get(url).json()["pendiente_de_aplicar"] is False


# --- Alertas y umbrales ---


def _fijar_umbral(cliente, tanque_id, **umbral):
    return cliente.put(f"/api/v1/tanques/{tanque_id}/umbrales", json={"umbrales": [umbral]})


def test_lectura_fuera_de_rango_abre_alerta_una_sola_vez_y_se_resuelve_con_histeresis(
    cliente_con_sesion, nodo_con_servo, sesion
):
    _fijar_umbral(
        cliente_con_sesion,
        nodo_con_servo.tanque_id,
        variable="temp_c",
        minimo=24,
        maximo=28,
        histeresis=0.5,
    )

    _reportar(cliente_con_sesion, nodo_con_servo, ["temp"], [("temp_c", 29, 0)])
    abierta = _alertas_activas(sesion)
    _reportar(cliente_con_sesion, nodo_con_servo, ["temp"], [("temp_c", 30, 0)])
    sin_duplicar = _alertas_activas(sesion)
    _reportar(cliente_con_sesion, nodo_con_servo, ["temp"], [("temp_c", 27.8, 0)])
    en_la_banda = _alertas_activas(sesion)
    _reportar(cliente_con_sesion, nodo_con_servo, ["temp"], [("temp_c", 27.4, 0)])

    assert [codigo for codigo, _ in abierta] == ["FUERA_DE_RANGO"]
    assert len(sin_duplicar) == 1
    assert len(en_la_banda) == 1
    assert _alertas_activas(sesion) == []


def test_alerta_aparece_en_el_panel_y_en_el_listado(cliente_con_sesion, nodo_con_servo):
    _reportar(cliente_con_sesion, nodo_con_servo, ["flotador"], [("flotador_bajo", 1, 0)])

    tanque = cliente_con_sesion.get("/api/v1/tanques").json()[0]
    listado = cliente_con_sesion.get(ALERTAS, params={"activa": "true"}).json()

    assert [a["tipo"] for a in tanque["alertas"]] == ["NIVEL_BAJO"]
    assert tanque["alertas"][0]["severidad"] == "critica"
    assert listado["total"] == 1
    assert listado["elementos"][0]["tanque_id"] == nodo_con_servo.tanque_id


def test_booleanas_abren_y_resuelven_al_volver_a_cero(cliente_con_sesion, nodo_con_servo, sesion):
    _reportar(cliente_con_sesion, nodo_con_servo, ["tolva"], [("tolva_vacia", 1, 0)])
    abierta = [codigo for codigo, _ in _alertas_activas(sesion)]

    _reportar(cliente_con_sesion, nodo_con_servo, ["tolva"], [("tolva_vacia", 0, 0)])

    assert abierta == ["TOLVA_VACIA"]
    assert _alertas_activas(sesion) == []
    historial = cliente_con_sesion.get(ALERTAS, params={"activa": "false"}).json()
    assert historial["elementos"][0]["resuelta_en"] is not None


def test_lectura_atrasada_no_reabre_ni_cierra_alertas(cliente_con_sesion, nodo_con_servo, sesion):
    _reportar(cliente_con_sesion, nodo_con_servo, ["flotador"], [("flotador_bajo", 0, 0)])
    hace_una_hora = int((datetime.now(UTC) - timedelta(hours=1)).timestamp() * 1000)
    cliente_con_sesion.post(
        TELEMETRIA,
        json={
            "lote": 3,
            "nodos": [{"mac": nodo_con_servo.mac, "boot": 7, "modulos": ["flotador"]}],
            "lecturas": [
                {
                    "mac": nodo_con_servo.mac,
                    "variable": "flotador_bajo",
                    "valor": 1,
                    "edad_ms": 0,
                    "boot": 6,
                    "epoch_ms": hace_una_hora,
                }
            ],
        },
        headers=_token(nodo_con_servo),
    )

    assert _alertas_activas(sesion) == []


def test_alertas_se_paginan_con_maximo_de_100(cliente_con_sesion):
    assert cliente_con_sesion.get(ALERTAS, params={"tamano": 101}).status_code == 422
    vacio = cliente_con_sesion.get(ALERTAS).json()
    assert vacio == {"elementos": [], "total": 0, "pagina": 1, "tamano": 20}


def test_umbrales_muestran_las_variables_numericas_del_nodo(cliente_con_sesion, nodo_con_servo):
    umbrales = cliente_con_sesion.get(f"/api/v1/tanques/{nodo_con_servo.tanque_id}/umbrales").json()

    assert [u["variable"] for u in umbrales] == ["temp_c", "distancia_tolva_cm"]
    assert umbrales[0]["minimo"] is None


@pytest.mark.parametrize(
    ("umbral", "motivo"),
    [
        ({"variable": "temp_c", "minimo": 28, "maximo": 24}, "MINIMO_NO_MENOR_QUE_MAXIMO"),
        (
            {"variable": "temp_c", "minimo": 24, "maximo": 28, "histeresis": 2},
            "HISTERESIS_DEMASIADO_GRANDE",
        ),
        ({"variable": "temp_c", "maximo": 500}, "FUERA_DE_RANGO_FISICO"),
        ({"variable": "flotador_bajo", "maximo": 1}, "VARIABLE_NO_NUMERICA"),
    ],
)
def test_umbral_invalido_responde_422(cliente_con_sesion, nodo_con_servo, umbral, motivo):
    respuesta = _fijar_umbral(cliente_con_sesion, nodo_con_servo.tanque_id, **umbral)

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["details"][0]["motivo"] == motivo


def test_umbral_sin_limites_se_elimina(cliente_con_sesion, nodo_con_servo):
    tanque = nodo_con_servo.tanque_id
    _fijar_umbral(cliente_con_sesion, tanque, variable="temp_c", minimo=24, maximo=28)

    respuesta = _fijar_umbral(
        cliente_con_sesion, tanque, variable="temp_c", minimo=None, maximo=None
    )

    assert respuesta.json()[0]["maximo"] is None


def test_umbrales_de_tanque_inexistente_responde_404(cliente_con_sesion):
    assert cliente_con_sesion.get("/api/v1/tanques/999/umbrales").status_code == 404
