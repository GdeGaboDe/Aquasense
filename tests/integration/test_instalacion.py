import hashlib
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.modelos import CambioAgua, Lectura, Nodo, Sensor, Variable

TANQUES = "/api/v1/tanques"
NODOS = "/api/v1/nodos"
MAC = "24:6F:28:AB:CD:EF"
TANQUE = {"nombre": "Betta", "volumen_l": 20.5, "especie": "Betta splendens"}


def _crear_tanque(cliente, **cambios) -> dict:
    respuesta = cliente.post(TANQUES, json=TANQUE | cambios)
    assert respuesta.status_code == 201
    return respuesta.json()


def _token(respuesta) -> str:
    return respuesta.json()["token"]


def test_rutas_exigen_sesion(cliente):
    assert cliente.get(TANQUES).status_code == 401
    assert cliente.post(TANQUES, json=TANQUE).status_code == 401
    assert cliente.patch(f"{TANQUES}/1", json={}).status_code == 401
    assert cliente.post(NODOS, json={}).status_code == 401
    assert cliente.patch(f"{NODOS}/1", json={}).status_code == 401


def test_lista_vacia_sin_tanques(cliente_con_sesion):
    assert cliente_con_sesion.get(TANQUES).json() == []


def test_alta_de_tanque_registra_el_cambio_de_agua_inicial(cliente_con_sesion, usuario, sesion):
    tanque = _crear_tanque(cliente_con_sesion)

    cambio = sesion.scalar(select(CambioAgua).where(CambioAgua.tanque_id == tanque["id"]))
    assert tanque["volumen_l"] == 20.5
    assert cambio is not None
    assert cambio.porcentaje == 100
    assert cambio.registrado_por == usuario.id


def test_nombre_de_tanque_duplicado_responde_409(cliente_con_sesion):
    _crear_tanque(cliente_con_sesion)

    respuesta = cliente_con_sesion.post(TANQUES, json=TANQUE)

    assert respuesta.status_code == 409
    assert respuesta.json()["error"]["code"] == "TANQUE_DUPLICADO"


def test_volumen_invalido_responde_422(cliente_con_sesion):
    respuesta = cliente_con_sesion.post(TANQUES, json=TANQUE | {"volumen_l": 0})

    assert respuesta.status_code == 422


def test_editar_tanque_cambia_solo_lo_enviado(cliente_con_sesion):
    tanque = _crear_tanque(cliente_con_sesion)

    respuesta = cliente_con_sesion.patch(f"{TANQUES}/{tanque['id']}", json={"especie": None})

    assert respuesta.status_code == 200
    assert respuesta.json()["especie"] is None
    assert respuesta.json()["nombre"] == "Betta"


def test_editar_tanque_no_permite_nombre_nulo(cliente_con_sesion):
    tanque = _crear_tanque(cliente_con_sesion)

    respuesta = cliente_con_sesion.patch(f"{TANQUES}/{tanque['id']}", json={"nombre": None})

    assert respuesta.status_code == 422


def test_editar_tanque_inexistente_responde_404(cliente_con_sesion):
    assert cliente_con_sesion.patch(f"{TANQUES}/999", json={"notas": "x"}).status_code == 404


def test_alta_de_autonomo_devuelve_token_y_solo_guarda_su_hash(cliente_con_sesion, sesion):
    tanque = _crear_tanque(cliente_con_sesion)

    respuesta = cliente_con_sesion.post(
        NODOS, json={"mac": MAC.lower(), "nombre": "Principal", "tanque_id": tanque["id"]}
    )

    assert respuesta.status_code == 201
    token = _token(respuesta)
    assert len(token) == 40
    nodo = sesion.get(Nodo, respuesta.json()["id"])
    assert nodo.mac == MAC
    assert nodo.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in nodo.token_hash


def test_token_del_alta_sirve_para_enviar_telemetria(cliente_con_sesion):
    tanque = _crear_tanque(cliente_con_sesion)
    alta = cliente_con_sesion.post(
        NODOS, json={"mac": MAC, "nombre": "Principal", "tanque_id": tanque["id"]}
    )

    respuesta = cliente_con_sesion.post(
        "/api/v1/device/telemetry",
        json={"lote": 1, "nodos": []},
        headers={"X-API-Token": _token(alta)},
    )

    assert respuesta.status_code == 200


def test_alta_de_satelite_no_tiene_token(cliente_con_sesion, crear_nodo):
    autonomo = crear_nodo()
    tanque = _crear_tanque(cliente_con_sesion)

    respuesta = cliente_con_sesion.post(
        NODOS,
        json={
            "mac": MAC,
            "nombre": "Satélite",
            "tanque_id": tanque["id"],
            "padre_id": autonomo.id,
        },
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["token"] is None
    assert respuesta.json()["padre_id"] == autonomo.id


def test_satelite_no_puede_ser_padre(cliente_con_sesion, crear_nodo):
    autonomo = crear_nodo()
    satelite = crear_nodo(padre_id=autonomo.id)
    tanque = _crear_tanque(cliente_con_sesion)

    respuesta = cliente_con_sesion.post(
        NODOS,
        json={"mac": MAC, "nombre": "N", "tanque_id": tanque["id"], "padre_id": satelite.id},
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["code"] == "PADRE_INVALIDO"


def test_alta_de_nodo_con_tanque_inexistente_responde_404(cliente_con_sesion):
    respuesta = cliente_con_sesion.post(NODOS, json={"mac": MAC, "nombre": "N", "tanque_id": 999})

    assert respuesta.status_code == 404


def test_mac_duplicada_responde_409(cliente_con_sesion, crear_nodo):
    existente = crear_nodo()
    tanque = _crear_tanque(cliente_con_sesion)

    respuesta = cliente_con_sesion.post(
        NODOS, json={"mac": existente.mac, "nombre": "N", "tanque_id": tanque["id"]}
    )

    assert respuesta.status_code == 409


def test_segundo_nodo_en_el_mismo_tanque_responde_409(cliente_con_sesion, crear_nodo):
    existente = crear_nodo()

    respuesta = cliente_con_sesion.post(
        NODOS, json={"mac": MAC, "nombre": "N", "tanque_id": existente.tanque_id}
    )

    assert respuesta.status_code == 409


def test_desactivar_nodo_impide_que_siga_enviando(cliente_con_sesion, crear_nodo):
    nodo = crear_nodo()

    edicion = cliente_con_sesion.patch(f"{NODOS}/{nodo.id}", json={"activo": False})
    envio = cliente_con_sesion.post(
        "/api/v1/device/telemetry",
        json={"lote": 1, "nodos": []},
        headers={"X-API-Token": nodo.token},
    )

    assert edicion.status_code == 200
    assert envio.status_code == 401


def test_tanque_sin_nodo_se_reporta_como_tal(cliente_con_sesion):
    _crear_tanque(cliente_con_sesion)

    tanque = cliente_con_sesion.get(TANQUES).json()[0]

    assert tanque["estado"] == "sin_nodo"
    assert tanque["nodo"] is None
    assert tanque["lecturas"] == []


def test_nodo_que_nunca_reporto_aparece_sin_conexion(cliente_con_sesion, crear_nodo):
    crear_nodo()

    assert cliente_con_sesion.get(TANQUES).json()[0]["estado"] == "sin_conexion"


def _reportar(cliente, nodo, lecturas: list[dict]) -> None:
    respuesta = cliente.post(
        "/api/v1/device/telemetry",
        json={
            "lote": 1,
            "nodos": [{"mac": nodo.mac, "boot": 7, "modulos": ["temp", "servo", "flotador"]}],
            "lecturas": lecturas,
        },
        headers={"X-API-Token": nodo.token},
    )
    assert respuesta.json()["rechazadas"] == []


def test_panel_muestra_la_ultima_lectura_de_cada_variable(cliente_con_sesion, crear_nodo):
    nodo = crear_nodo()
    base = {"mac": nodo.mac, "boot": 7, "epoch_ms": None}
    _reportar(
        cliente_con_sesion,
        nodo,
        [
            base | {"variable": "temp_c", "valor": 20, "edad_ms": 5000},
            base | {"variable": "temp_c", "valor": 25.4, "edad_ms": 100},
            base | {"variable": "flotador_bajo", "valor": 0, "edad_ms": 100},
        ],
    )

    tanque = cliente_con_sesion.get(TANQUES).json()[0]

    assert tanque["estado"] == "en_linea"
    assert tanque["nodo"]["modulos"] == ["flotador", "servo", "temp"]
    lecturas = {lectura["variable"]: lectura for lectura in tanque["lecturas"]}
    assert lecturas["temp_c"]["valor"] == 25.4
    assert lecturas["temp_c"]["unidad"] == "°C"
    assert lecturas["flotador_bajo"]["tipo"] == "booleano"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", lecturas["temp_c"]["medido_en"])


def test_panel_excluye_lecturas_con_hora_desconocida(cliente_con_sesion, crear_nodo, sesion):
    nodo = crear_nodo()
    _reportar(
        cliente_con_sesion,
        nodo,
        [{"mac": nodo.mac, "variable": "temp_c", "valor": 30, "edad_ms": 0, "boot": 6}],
    )
    guardada = sesion.scalar(select(Lectura))
    assert guardada.origen_hora == "desconocida"

    assert cliente_con_sesion.get(TANQUES).json()[0]["lecturas"] == []


def test_nodo_que_dejo_de_reportar_pasa_a_sin_conexion(cliente_con_sesion, crear_nodo, sesion):
    nodo = crear_nodo()
    _reportar(cliente_con_sesion, nodo, [])
    guardado = sesion.get(Nodo, nodo.id)
    sesion.refresh(guardado)
    guardado.ultimo_contacto = datetime.now(UTC) - timedelta(seconds=31)
    sesion.commit()

    assert cliente_con_sesion.get(TANQUES).json()[0]["estado"] == "sin_conexion"


def test_sensor_creado_apunta_al_catalogo(cliente_con_sesion, crear_nodo, sesion):
    nodo = crear_nodo()
    _reportar(cliente_con_sesion, nodo, [])

    codigos = set(
        sesion.scalars(
            select(Variable.codigo)
            .join(Sensor, Sensor.variable_id == Variable.id)
            .where(Sensor.nodo_id == nodo.id)
        )
    )

    assert codigos == {"temp_c", "flotador_bajo"}
