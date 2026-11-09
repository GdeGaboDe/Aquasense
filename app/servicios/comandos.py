"""Creación, expiración y consulta de comandos (CLAUDE.md, 7.3)."""

from collections.abc import Iterable
from datetime import datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.dominio import comandos as reglas
from app.esquemas.control import ComandoCrear, ComandoSalida, Pagina
from app.modelos import Comando, EstadoComando, Nodo, TipoComando, Usuario
from app.repositorios import control as repo
from app.repositorios.ingesta import modulos_de_nodo
from app.servicios import alertas
from app.servicios.errores import ErrorDeNegocio

_DETALLE_EXPIRADO = "No se entregó al nodo antes de expirar."
_CODIGO_HTTP_POR_MOTIVO = {
    "MODULO_NO_DISPONIBLE": status.HTTP_400_BAD_REQUEST,
    "ARGUMENTO_INVALIDO": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "TIPO_DESCONOCIDO": status.HTTP_422_UNPROCESSABLE_CONTENT,
}
_MENSAJES = {
    "MODULO_NO_DISPONIBLE": "El nodo no tiene el módulo que requiere este comando.",
    "ARGUMENTO_INVALIDO": "El argumento está fuera del rango permitido para este comando.",
    "TIPO_DESCONOCIDO": "Tipo de comando desconocido.",
}


def expirar_vencidos(
    sesion: Session, ahora: datetime, nodo_ids: Iterable[int] | None = None
) -> None:
    """Marca como expirados los pendientes vencidos; se hace al consultar, sin tareas de fondo."""
    for comando in repo.pendientes_vencidos(sesion, ahora, nodo_ids):
        comando.estado = EstadoComando.EXPIRADO
        comando.resuelto_en = comando.expira_en
        comando.detalle = _DETALLE_EXPIRADO
        nodo = sesion.get(Nodo, comando.nodo_id)
        if nodo is not None:
            alertas.abrir_por_comando(sesion, comando, nodo.tanque_id, comando.expira_en)


def a_salida(comando: Comando, ahora: datetime) -> ComandoSalida:
    return ComandoSalida(
        id=comando.id,
        nodo_id=comando.nodo_id,
        tipo=comando.tipo.value,
        argumento=comando.argumento,
        estado=reglas.estado_mostrado(comando.estado.value, comando.entregado_en, ahora),
        creado_en=comando.creado_en,
        expira_en=comando.expira_en,
        entregado_en=comando.entregado_en,
        resuelto_en=comando.resuelto_en,
        detalle=comando.detalle,
    )


def crear(sesion: Session, datos: ComandoCrear, usuario: Usuario, ahora: datetime) -> ComandoSalida:
    # Bloquea la fila del nodo: dos clics simultáneos en "Dispensar" no pueden pasar ambos.
    nodo = sesion.get(Nodo, datos.nodo_id, with_for_update=True)
    if nodo is None:
        raise ErrorDeNegocio(status.HTTP_404_NOT_FOUND, "NODO_NO_ENCONTRADO", "No existe ese nodo.")
    if not nodo.activo:
        raise ErrorDeNegocio(status.HTTP_409_CONFLICT, "NODO_INACTIVO", "El nodo está desactivado.")

    motivo = reglas.motivo_comando_invalido(
        datos.tipo, datos.argumento, modulos_de_nodo(sesion, nodo.id)
    )
    if motivo is not None:
        raise ErrorDeNegocio(_CODIGO_HTTP_POR_MOTIVO[motivo], motivo, _MENSAJES[motivo])

    expirar_vencidos(sesion, ahora, [nodo.id])
    if datos.tipo == reglas.DISPENSAR and any(
        reglas.bloquea_otro_dispensar(c.estado.value, c.entregado_en, ahora)
        for c in repo.dispensar_en_curso(sesion, nodo.id)
    ):
        raise ErrorDeNegocio(
            status.HTTP_409_CONFLICT,
            "DISPENSAR_EN_CURSO",
            "Ya hay una alimentación en curso para este nodo. Espera a que termine.",
        )

    comando = Comando(
        nodo_id=nodo.id,
        tipo=TipoComando(datos.tipo),
        argumento=datos.argumento,
        estado=EstadoComando.PENDIENTE,
        creado_por=usuario.id,
        creado_en=ahora,
        expira_en=ahora + reglas.EXPIRACION_PENDIENTE,
    )
    sesion.add(comando)
    sesion.commit()
    return a_salida(comando, ahora)


def listar(
    sesion: Session, nodo_id: int | None, pagina: int, tamano: int, ahora: datetime
) -> Pagina[ComandoSalida]:
    expirar_vencidos(sesion, ahora, None if nodo_id is None else [nodo_id])
    sesion.commit()
    filas, total = repo.listar_comandos(sesion, nodo_id, (pagina - 1) * tamano, tamano)
    return Pagina(
        elementos=[a_salida(c, ahora) for c in filas], total=total, pagina=pagina, tamano=tamano
    )
