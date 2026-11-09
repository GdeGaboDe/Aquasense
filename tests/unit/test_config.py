import pytest
from pydantic import ValidationError

from app.config import Settings

_BASE = {
    "database_url": "mysql+pymysql://u:p@h/b",
    "migraciones_database_url": "mysql+pymysql://m:p@h/b",
    "secret_key": "x" * 64,
}


def _settings(**cambios: object) -> Settings:
    return Settings(_env_file=None, **{**_BASE, **cambios})


def test_separa_hosts_permitidos_por_coma_e_ignora_espacios(monkeypatch):
    monkeypatch.setenv("HOSTS_PERMITIDOS", "aquasense.ejemplo.com, 192.168.1.50 ,localhost")

    settings = _settings()

    assert settings.hosts_permitidos == ["aquasense.ejemplo.com", "192.168.1.50", "localhost"]


def test_rechaza_secret_key_corta():
    with pytest.raises(ValidationError):
        _settings(secret_key="corta")


def test_exige_la_url_de_la_base(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    datos = {k: v for k, v in _BASE.items() if k != "database_url"}

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **datos)


def test_por_defecto_es_produccion_con_docs_cerradas_y_dispositivo_solo_lan(monkeypatch):
    for variable in ("ENTORNO", "DOCS_PUBLICAS", "DISPOSITIVO_SOLO_LAN"):
        monkeypatch.delenv(variable, raising=False)

    settings = _settings()

    assert settings.entorno == "produccion"
    assert settings.docs_publicas is False
    assert settings.dispositivo_solo_lan is True


def test_ips_de_proxy_confiables_por_defecto_son_solo_locales(monkeypatch):
    monkeypatch.delenv("IPS_PROXY_CONFIABLES", raising=False)

    assert _settings().ips_proxy_confiables == ["127.0.0.1", "::1"]


def test_ips_de_proxy_confiables_se_separan_por_coma(monkeypatch):
    monkeypatch.setenv("IPS_PROXY_CONFIABLES", "172.30.42.10, 127.0.0.1")

    assert _settings().ips_proxy_confiables == ["172.30.42.10", "127.0.0.1"]
