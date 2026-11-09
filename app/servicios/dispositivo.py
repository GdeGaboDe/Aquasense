"""Configuración y comandos para el autónomo, y sus confirmaciones (CLAUDE.md, 6.2 y 6.3)."""

from datetime import datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.dominio import comandos as reglas
from app.dominio.parametros import convertir_para_nodo
from app.esquemas.control import Ack, ComandoParaNodo, ConfigNodo, RespuestaAck, RespuestaConfig
from app.modelos import Comando, EstadoComando, Nodo
from app.repositorios import control as repo
from app.repositorios.ingesta import nodos_de_autonomo
from app.repositorios.instalacion import modulos_por_nodo
from app.servicios import alertas
from app.servicios.comandos import expirar_vencidos
from app.servicios.errores import ErrorDeNegocio
from app.servicios.parametros import efectivos

_MS_POR_SEGUNDO = 1000


def obtener_config(sesion: Session, autonomo: Nodo, ahora: datetime) -> RespuestaConfig:
    """Configuración del autónomo y sus satélites. Entregar un comando lo marca como entregado."""
    nodos = [n for n in nodos_de_autonomo(sesion, autonomo.id) if n.activo]
    ids = [n.id for n in nodos]
    expirar_vencidos(sesion, ahora, ids)

    catalogo = repo.catalogo_de_parametros(sesion)
    modulos = modulos_por_nodo(sesion, ids)
    guardados = repo.valores_de_nodos(sesion, ids)
    configuracion = []
    for nodo in nodos:
        vigentes = efectivos(catalogo, set(modulos.get(nodo.id, [])), guardados.get(nodo.id, {}))
        configuracion.append(
            ConfigNodo(
                mac=nodo.mac,
                config_version=nodo.config_version,
                parametros={
                    codigo: convertir_para_nodo(item.definicion, item.valor)
                    for codigo, item in vigentes.items()
                },
            )
        )

    mac_por_id = {n.id: n.mac for n in nodos}
    entregados = []
    for comando in repo.pendientes_de_nodos(sesion, ids):
        comando.estado = EstadoComando.ENTREGADO
        comando.entregado_en = ahora
        entregados.append(
            ComandoParaNodo(
                id=comando.id,
                mac=mac_por_id[comando.nodo_id],
                tipo=comando.tipo.value,
                argumento=comando.argumento,
            )
        )
    sesion.commit()
    return RespuestaConfig(
        servidor_epoch_ms=int(ahora.timestamp() * _MS_POR_SEGUNDO),
        nodos=configuracion,
        comandos=entregados,
    )


def registrar_ack(sesion: Session, autonomo: Nodo, ack: Ack, ahora: datetime) -> RespuestaAck:
    comando = sesion.get(Comando, ack.comando_id, with_for_update=True)
    if comando is None:
        raise ErrorDeNegocio(
            status.HTTP_404_NOT_FOUND, "COMANDO_NO_ENCONTRADO", "No existe ese comando."
        )
    propios = {n.id: n for n in nodos_de_autonomo(sesion, autonomo.id)}
    if comando.nodo_id not in propios:
        raise ErrorDeNegocio(
            status.HTTP_403_FORBIDDEN,
            "COMANDO_AJENO",
            "El comando no pertenece a los nodos de este autónomo.",
        )

    try:
        nuevo = reglas.estado_a_aplicar(comando.estado.value, ack.resultado)
    except reglas.TransicionInvalida as error:
        raise ErrorDeNegocio(
            status.HTTP_409_CONFLICT,
            "ACK_INVALIDO",
            f"El comando está {comando.estado.value}; no admite un ACK {ack.resultado}.",
        ) from error

    if nuevo is not None:
        comando.estado = EstadoComando(nuevo)
        comando.resuelto_en = ahora
        comando.detalle = ack.detalle
        tanque_id = propios[comando.nodo_id].tanque_id
        if nuevo == reglas.FALLIDO:
            alertas.abrir_por_comando(sesion, comando, tanque_id, ahora)
        else:
            alertas.resolver_por_comando_exitoso(sesion, tanque_id, ahora)
        sesion.commit()
    return RespuestaAck(comando_id=comando.id, estado=comando.estado.value)
