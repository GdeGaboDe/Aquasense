from fastapi.testclient import TestClient

from tests.integration.conftest import CONTRASENA_DE_PRUEBA, USUARIO_DE_PRUEBA

LOGIN = "/api/v1/auth/login"
INCORRECTAS = {"usuario": USUARIO_DE_PRUEBA, "contrasena": "contrasena-equivocada"}
CORRECTAS = {"usuario": USUARIO_DE_PRUEBA, "contrasena": CONTRASENA_DE_PRUEBA}


def test_host_no_permitido_responde_400(cliente):
    respuesta = cliente.get("/health", headers={"Host": "sitio-malicioso.com"})

    assert respuesta.status_code == 400


def test_respuestas_llevan_encabezados_de_seguridad(cliente):
    encabezados = cliente.get("/health").headers

    assert "frame-ancestors 'none'" in encabezados["content-security-policy"]
    assert encabezados["x-content-type-options"] == "nosniff"
    assert encabezados["referrer-policy"] == "same-origin"
    assert "strict-transport-security" not in encabezados


def test_errores_tambien_llevan_encabezados_de_seguridad(cliente):
    encabezados = cliente.get("/api/v1/tanques").headers

    assert encabezados["x-content-type-options"] == "nosniff"


def test_error_inesperado_no_revela_detalles_y_lleva_encabezados(
    crear_cliente, sesion, monkeypatch
):
    def fallar(*_args, **_kwargs):
        raise RuntimeError("detalle-interno")

    monkeypatch.setattr("app.api.auth.autenticar", fallar)
    cliente = crear_cliente(raise_server_exceptions=False)

    respuesta = cliente.post(LOGIN, json=CORRECTAS)

    assert respuesta.status_code == 500
    assert respuesta.json()["error"]["code"] == "ERROR_INTERNO"
    assert "detalle-interno" not in respuesta.text
    assert respuesta.headers["x-content-type-options"] == "nosniff"


def test_por_https_agrega_hsts_y_marca_la_cookie_como_secure(crear_cliente, usuario):
    cliente = crear_cliente(base_url="https://testserver")

    respuesta = cliente.post(LOGIN, json=CORRECTAS)

    assert "max-age" in respuesta.headers["strict-transport-security"]
    cookie = respuesta.headers["set-cookie"].lower()
    assert "secure" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie


def test_por_http_de_la_red_local_la_cookie_no_es_secure(cliente, usuario):
    respuesta = cliente.post(LOGIN, json=CORRECTAS)

    assert "secure" not in respuesta.headers["set-cookie"].lower()


def test_sexto_intento_de_login_en_un_minuto_responde_429(cliente, usuario):
    codigos = [cliente.post(LOGIN, json=INCORRECTAS).status_code for _ in range(6)]

    assert codigos == [401] * 5 + [429]


def test_respuesta_429_usa_el_formato_de_error(cliente, usuario):
    for _ in range(5):
        cliente.post(LOGIN, json=INCORRECTAS)

    respuesta = cliente.post(LOGIN, json=INCORRECTAS)

    assert respuesta.json()["error"]["code"] == "DEMASIADAS_PETICIONES"


def test_cf_connecting_ip_se_ignora_si_no_viene_de_127_0_0_1(cliente, usuario):
    codigos = [
        cliente.post(
            LOGIN, json=INCORRECTAS, headers={"CF-Connecting-IP": f"8.8.8.{numero}"}
        ).status_code
        for numero in range(6)
    ]

    assert codigos[-1] == 429


def test_cf_connecting_ip_identifica_al_cliente_si_viene_del_tunel(crear_cliente, usuario):
    cliente: TestClient = crear_cliente(ip="127.0.0.1")

    codigos = [
        cliente.post(
            LOGIN, json=INCORRECTAS, headers={"CF-Connecting-IP": f"8.8.8.{numero}"}
        ).status_code
        for numero in range(6)
    ]

    assert codigos == [401] * 6


def test_api_web_limita_a_120_peticiones_por_minuto(cliente, usuario):
    codigos = [cliente.get("/api/v1/tanques").status_code for _ in range(121)]

    assert codigos[119] == 401
    assert codigos[120] == 429


def test_health_no_requiere_sesion(cliente):
    assert cliente.get("/health").status_code == 200


def test_robots_prohibe_indexar(cliente):
    respuesta = cliente.get("/robots.txt")

    assert "Disallow: /" in respuesta.text
