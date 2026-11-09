"""Configuración de la aplicación, leída del entorno y de .env."""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Entorno(StrEnum):
    DESARROLLO = "desarrollo"
    PRODUCCION = "produccion"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    entorno: Entorno = Entorno.PRODUCCION
    database_url: str
    migraciones_database_url: str
    secret_key: str = Field(min_length=32)
    hosts_permitidos: Annotated[list[str], NoDecode] = ["localhost"]
    # IP desde la que llega cloudflared: solo de ella se cree CF-Connecting-IP. En Docker es la IP
    # fija del contenedor del túnel; uvicorn recibe el mismo valor por FORWARDED_ALLOW_IPS.
    ips_proxy_confiables: Annotated[list[str], NoDecode] = ["127.0.0.1", "::1"]
    dispositivo_solo_lan: bool = True
    docs_publicas: bool = False
    sesion_horas: int = Field(default=8, gt=0)
    zona_horaria_web: str = "America/Mexico_City"
    polling_panel_s: int = Field(default=10, gt=0)
    polling_graficas_s: int = Field(default=60, gt=0)
    polling_comando_s: int = Field(default=3, gt=0)

    @field_validator("hosts_permitidos", "ips_proxy_confiables", mode="before")
    @classmethod
    def _separar_hosts(cls, valor: object) -> object:
        if isinstance(valor, str):
            return [host.strip() for host in valor.split(",") if host.strip()]
        return valor


@lru_cache
def obtener_settings() -> Settings:
    return Settings()
