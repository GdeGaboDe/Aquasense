import json
import time
from base64 import b64encode

from itsdangerous import TimestampSigner

from app.config import obtener_settings
from tests.integration.conftest import CONTRASENA_DE_PRUEBA, USUARIO_DE_PRUEBA

LOGIN = "/api/v1/auth/login"
YO = "/api/v1/auth/yo"
CORRECTAS = {"usuario": USUARIO_DE_PRUEBA, "contrasena": CONTRASENA_DE_PRUEBA}


def test_login_correcto_entrega_datos_del_usuario_y_registra_el_acceso(cliente, usuario, sesion):
    respuesta = cliente.post(LOGIN, json=CORRECTAS)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "usuario": USUARIO_DE_PRUEBA,
        "polling_panel_s": 10,
        "polling_graficas_s": 60,
        "polling_comando_s": 3,
        "zona_horaria": "America/Mexico_City",
    }
    sesion.refresh(usuario)
    assert usuario.ultimo_acceso is not None


def test_contrasena_incorrecta_responde_401(cliente, usuario):
    respuesta = cliente.post(LOGIN, json={"usuario": USUARIO_DE_PRUEBA, "contrasena": "mala"})

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "CREDENCIALES_INVALIDAS"


def test_usuario_inexistente_responde_igual_que_contrasena_incorrecta(cliente, usuario):
    inexistente = cliente.post(LOGIN, json={"usuario": "nadie", "contrasena": "mala"})
    incorrecta = cliente.post(LOGIN, json={"usuario": USUARIO_DE_PRUEBA, "contrasena": "mala"})

    assert inexistente.status_code == incorrecta.status_code
    assert inexistente.json() == incorrecta.json()


def test_contrasena_de_mas_de_72_bytes_responde_401_sin_fallar(cliente, usuario):
    respuesta = cliente.post(LOGIN, json={"usuario": USUARIO_DE_PRUEBA, "contrasena": "x" * 100})

    assert respuesta.status_code == 401


def test_yo_sin_sesion_responde_401(cliente):
    assert cliente.get(YO).status_code == 401


def test_yo_con_sesion_responde_el_usuario(cliente_con_sesion):
    assert cliente_con_sesion.get(YO).json()["usuario"] == USUARIO_DE_PRUEBA


def test_logout_invalida_tambien_las_copias_de_la_cookie(cliente_con_sesion, crear_cliente):
    cookie = cliente_con_sesion.cookies["aquasense_sesion"]

    respuesta = cliente_con_sesion.post("/api/v1/auth/logout")

    assert respuesta.status_code == 204
    assert cliente_con_sesion.get(YO).status_code == 401
    copia = crear_cliente(cookies={"aquasense_sesion": cookie})
    assert copia.get(YO).status_code == 401


def _cookie_firmada(datos: dict) -> str:
    """Cookie con firma válida y reciente, como la que renueva SessionMiddleware."""
    contenido = b64encode(json.dumps(datos).encode())
    return TimestampSigner(obtener_settings().secret_key).sign(contenido).decode()


def test_sesion_expira_a_las_8_horas_aunque_la_cookie_se_haya_renovado(crear_cliente, usuario):
    hace_mas_de_8_horas = int(time.time()) - 8 * 3600 - 1
    cookie = _cookie_firmada(
        {"usuario_id": usuario.id, "version": 1, "iniciada_en": hace_mas_de_8_horas}
    )

    respuesta = crear_cliente(cookies={"aquasense_sesion": cookie}).get(YO)

    assert respuesta.status_code == 401


def test_sesion_sigue_vigente_antes_de_las_8_horas(crear_cliente, usuario):
    hace_7_horas = int(time.time()) - 7 * 3600
    cookie = _cookie_firmada({"usuario_id": usuario.id, "version": 1, "iniciada_en": hace_7_horas})

    respuesta = crear_cliente(cookies={"aquasense_sesion": cookie}).get(YO)

    assert respuesta.status_code == 200


def test_cookie_alterada_no_da_acceso(crear_cliente, usuario):
    cliente = crear_cliente(cookies={"aquasense_sesion": "cookie.falsa.firmada"})

    assert cliente.get(YO).status_code == 401
