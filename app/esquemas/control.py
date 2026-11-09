"""Contratos de alertas, comandos, parámetros, umbrales y dosis."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.esquemas.web import FechaIso

MAX_POR_PAGINA = 100

ValorUmbral = Annotated[Decimal, Field(max_digits=10, decimal_places=3)]
ValorParametroEntrada = int | float | str


class Pagina[T](BaseModel):
    elementos: list[T]
    total: int
    pagina: int
    tamano: int


class AlertaSalida(BaseModel):
    id: int
    tanque_id: int
    tanque: str
    tipo: str
    descripcion: str
    severidad: Literal["info", "advertencia", "critica"]
    variable: str | None
    variable_nombre: str | None
    unidad: str | None
    valor: float | None
    iniciada_en: FechaIso
    resuelta_en: FechaIso | None
    activa: bool


class ComandoCrear(BaseModel):
    nodo_id: int = Field(ge=1)
    tipo: Literal["DISPENSAR", "SILENCIAR_ALARMA", "AIREADOR"]
    argumento: int | None = Field(default=None, ge=0, le=1000)


class ComandoSalida(BaseModel):
    id: int
    nodo_id: int
    tipo: str
    argumento: int | None
    estado: Literal["pendiente", "entregado", "sin_confirmar", "confirmado", "fallido", "expirado"]
    creado_en: FechaIso
    expira_en: FechaIso
    entregado_en: FechaIso | None
    resuelto_en: FechaIso | None
    detalle: str | None


class ParametroSalida(BaseModel):
    codigo: str
    descripcion: str
    tipo: Literal["entero", "decimal", "opcion"]
    unidad: str | None
    minimo: float | None
    maximo: float | None
    opciones: list[str] | None
    valor: int | float | str
    valor_defecto: int | float | str
    personalizado: bool


class ParametrosNodo(BaseModel):
    nodo_id: int
    config_version: int
    config_version_aplicada: int | None
    pendiente_de_aplicar: bool
    parametros: list[ParametroSalida]


class ParametrosEditar(BaseModel):
    valores: dict[Annotated[str, Field(max_length=40)], ValorParametroEntrada] = Field(
        min_length=1, max_length=30
    )


class UmbralSalida(BaseModel):
    variable: str
    nombre: str
    unidad: str | None
    min_fisico: float | None
    max_fisico: float | None
    minimo: float | None
    maximo: float | None
    histeresis: float


class UmbralEditar(BaseModel):
    variable: str = Field(max_length=40)
    minimo: ValorUmbral | None = None
    maximo: ValorUmbral | None = None
    histeresis: ValorUmbral = Decimal(0)


class UmbralesEditar(BaseModel):
    umbrales: list[UmbralEditar] = Field(min_length=1, max_length=20)


class DosisSalida(BaseModel):
    id: int
    nodo_id: int
    cargas: int
    origen: Literal["remoto", "automatico", "local"]
    dosificada_en: FechaIso
    comando_id: int | None


# --- Dispositivo (CLAUDE.md, 6.2 y 6.3) ---


class ConfigNodo(BaseModel):
    mac: str
    config_version: int
    parametros: dict[str, int | float | str]


class ComandoParaNodo(BaseModel):
    id: int
    mac: str
    tipo: str
    argumento: int | None


class RespuestaConfig(BaseModel):
    servidor_epoch_ms: int
    nodos: list[ConfigNodo]
    comandos: list[ComandoParaNodo]


class Ack(BaseModel):
    comando_id: int = Field(ge=1)
    resultado: Literal["confirmado", "fallido"]
    detalle: str | None = Field(default=None, max_length=200)


class RespuestaAck(BaseModel):
    comando_id: int
    estado: str
