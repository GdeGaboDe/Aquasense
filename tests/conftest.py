"""Prepara el entorno ANTES de importar la app, para que nunca toque la base de desarrollo."""

import os

from dotenv import load_dotenv

load_dotenv()

_URL_SIN_BASE = "mysql+pymysql://sin_base:sin_base@127.0.0.1:1/sin_base_test"
_url_pruebas = os.environ.get("TEST_DATABASE_URL", _URL_SIN_BASE)

os.environ["DATABASE_URL"] = _url_pruebas
os.environ["MIGRACIONES_DATABASE_URL"] = _url_pruebas
os.environ["SECRET_KEY"] = "clave-solo-para-pruebas-" + "x" * 40
os.environ["DOCS_PUBLICAS"] = "false"
os.environ["DISPOSITIVO_SOLO_LAN"] = "true"
os.environ["HOSTS_PERMITIDOS"] = "testserver,localhost"
