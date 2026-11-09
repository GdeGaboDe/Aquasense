"""Parámetros por nodo: consulta, validación y cambio de versión (CLAUDE.md, 7.4)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.dominio import parametros as reglas
from app.esquemas.control import ParametroSalida, ParametrosEditar, ParametrosNodo
from app.modelos import Nodo, Parametro, Usuario, ValorParametro
from app.repositorios import control as repo
from app.repositorios.ingesta import modulos_de_nodo
from app.servicios.errores import ErrorDeNegocio


@dataclass(frozen=True)
class ParametroEfectivo:
    fila: Parametro
    definicion: reglas.DefinicionParametro
    valor: str
    personalizado: bool


def _definicion(fila: Parametro) -> reglas.DefinicionParametro:
    return reglas.DefinicionParametro(
        codigo=fila.codigo,
        tipo=fila.tipo.value,
        minimo=fila.minimo,
        maximo=fila.maximo,
        opciones=tuple(fila.opciones) if fila.opciones else None,
        valor_defecto=fila.valor_defecto,
        modulo_requerido=fila.modulo_requerido,
    )


def efectivos(
    catalogo: Sequence[Parametro], modulos: set[str], guardados: dict[int, ValorParametro]
) -> dict[str, ParametroEfectivo]:
    """Valor vigente de cada parámetro que aplica al nodo: el guardado, o el de fábrica."""
    resultado = {}
    for fila in catalogo:
        definicion = _definicion(fila)
        if not reglas.aplica_al_nodo(definicion, modulos):
            continue
        guardado = guardados.get(fila.id)
        resultado[fila.codigo] = ParametroEfectivo(
            fila=fila,
            definicion=definicion,
            valor=guardado.valor if guardado else fila.valor_defecto,
            personalizado=guardado is not None,
        )
    return resultado


def _obtener_nodo(sesion: Session, nodo_id: int, bloquear: bool = False) -> Nodo:
    nodo = sesion.get(Nodo, nodo_id, with_for_update=bloquear)
    if nodo is None:
        raise ErrorDeNegocio(status.HTTP_404_NOT_FOUND, "NODO_NO_ENCONTRADO", "No existe ese nodo.")
    return nodo


def _a_salida(nodo: Nodo, vigentes: dict[str, ParametroEfectivo]) -> ParametrosNodo:
    parametros = []
    for item in vigentes.values():
        fila, definicion = item.fila, item.definicion
        parametros.append(
            ParametroSalida(
                codigo=fila.codigo,
                descripcion=fila.descripcion,
                tipo=definicion.tipo,
                unidad=fila.unidad,
                minimo=float(fila.minimo) if fila.minimo is not None else None,
                maximo=float(fila.maximo) if fila.maximo is not None else None,
                opciones=list(definicion.opciones) if definicion.opciones else None,
                valor=reglas.convertir_para_nodo(definicion, item.valor),
                valor_defecto=reglas.convertir_para_nodo(definicion, fila.valor_defecto),
                personalizado=item.personalizado,
            )
        )
    aplicada = nodo.config_version_aplicada
    return ParametrosNodo(
        nodo_id=nodo.id,
        config_version=nodo.config_version,
        config_version_aplicada=aplicada,
        pendiente_de_aplicar=aplicada is None or aplicada < nodo.config_version,
        parametros=parametros,
    )


def obtener(sesion: Session, nodo_id: int) -> ParametrosNodo:
    nodo = _obtener_nodo(sesion, nodo_id)
    vigentes = efectivos(
        repo.catalogo_de_parametros(sesion),
        modulos_de_nodo(sesion, nodo.id),
        repo.valores_de_nodos(sesion, [nodo.id]).get(nodo.id, {}),
    )
    return _a_salida(nodo, vigentes)


def actualizar(
    sesion: Session, nodo_id: int, datos: ParametrosEditar, usuario: Usuario, ahora: datetime
) -> ParametrosNodo:
    """Valida todo antes de guardar y sube `config_version` una vez, en la misma transacción."""
    nodo = _obtener_nodo(sesion, nodo_id, bloquear=True)
    catalogo = repo.catalogo_de_parametros(sesion)
    guardados = repo.valores_de_nodos(sesion, [nodo.id]).get(nodo.id, {})
    vigentes = efectivos(catalogo, modulos_de_nodo(sesion, nodo.id), guardados)
    conocidos = {fila.codigo for fila in catalogo}

    problemas: list[dict[str, str]] = []
    nuevos: dict[str, str] = {}
    for codigo, valor in datos.valores.items():
        if codigo not in conocidos:
            problemas.append({"parametro": codigo, "motivo": "PARAMETRO_DESCONOCIDO"})
        elif codigo not in vigentes:
            problemas.append({"parametro": codigo, "motivo": "MODULO_NO_DISPONIBLE"})
        elif (normalizado := reglas.normalizar(vigentes[codigo].definicion, valor)) is None:
            problemas.append({"parametro": codigo, "motivo": "VALOR_INVALIDO"})
        else:
            nuevos[codigo] = normalizado

    combinados = {codigo: item.valor for codigo, item in vigentes.items()} | nuevos
    if not problemas:
        problemas = [
            {"parametro": p.parametro, "motivo": p.motivo}
            for p in reglas.problemas_entre_parametros(combinados)
        ]
    if problemas:
        raise ErrorDeNegocio(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "PARAMETROS_INVALIDOS",
            "Algunos parámetros no son válidos; no se guardó ningún cambio.",
            problemas,
        )

    hubo_cambios = False
    for codigo, valor in nuevos.items():
        item = vigentes[codigo]
        guardado = guardados.get(item.fila.id)
        if item.valor == valor and guardado is not None:
            continue
        hubo_cambios = hubo_cambios or item.valor != valor
        if guardado is None:
            sesion.add(
                ValorParametro(
                    nodo_id=nodo.id,
                    parametro_id=item.fila.id,
                    valor=valor,
                    modificado_en=ahora,
                    modificado_por=usuario.id,
                )
            )
        else:
            guardado.valor = valor
            guardado.modificado_en = ahora
            guardado.modificado_por = usuario.id
    if hubo_cambios:
        nodo.config_version += 1
    sesion.commit()
    return obtener(sesion, nodo.id)
