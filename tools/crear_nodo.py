"""Da de alta un nodo y muestra su token UNA sola vez.

Autónomo con tanque nuevo:
    python -m tools.crear_nodo --mac 24:6F:28:AB:CD:EF --nombre Principal \
        --tanque Betta --volumen-l 20 --usuario admin
Satélite de ese autónomo:
    python -m tools.crear_nodo --mac 24:6F:28:11:22:33 --nombre Sat1 \
        --tanque Goldfish --volumen-l 60 --usuario admin --padre 24:6F:28:AB:CD:EF
"""

import argparse
import sys
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import ValidationError

from app.db import obtener_fabrica_sesiones
from app.esquemas.web import NodoCrear, TanqueCrear
from app.repositorios import instalacion as repo
from app.servicios import instalacion as servicio
from app.servicios.errores import ErrorDeNegocio


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Da de alta un nodo de AquaSense.")
    parser.add_argument("--mac", required=True, help="MAC del ESP32, p. ej. 24:6F:28:AB:CD:EF")
    parser.add_argument("--nombre", required=True, help="nombre del nodo")
    parser.add_argument("--tanque", required=True, help="tanque; se crea si no existe")
    parser.add_argument("--volumen-l", type=Decimal, help="litros, si el tanque es nuevo")
    parser.add_argument("--usuario", help="administrador que registra el tanque nuevo")
    parser.add_argument("--padre", help="MAC del autónomo; omítela para crear un autónomo")
    return parser


def _obtener_tanque_id(sesion, argumentos: argparse.Namespace) -> int:
    tanque = repo.buscar_tanque_por_nombre(sesion, argumentos.tanque)
    if tanque is not None:
        return tanque.id
    if argumentos.volumen_l is None or argumentos.usuario is None:
        raise ValueError("Para un tanque nuevo indica --volumen-l y --usuario.")
    usuario = repo.buscar_usuario(sesion, argumentos.usuario)
    if usuario is None:
        raise ValueError(f"No existe el usuario {argumentos.usuario}. Usa tools.crear_admin.")
    datos = TanqueCrear(nombre=argumentos.tanque, volumen_l=argumentos.volumen_l)
    return servicio.crear_tanque(sesion, datos, usuario.id, datetime.now(UTC)).id


def _obtener_padre_id(sesion, mac: str | None) -> int | None:
    if mac is None:
        return None
    padre = repo.buscar_nodo_por_mac(sesion, mac.upper())
    if padre is None:
        raise ValueError(f"No existe un nodo con la MAC {mac}.")
    return padre.id


def main() -> int:
    argumentos = _crear_parser().parse_args()
    try:
        with obtener_fabrica_sesiones()() as sesion:
            padre_id = _obtener_padre_id(sesion, argumentos.padre)
            tanque_id = _obtener_tanque_id(sesion, argumentos)
            datos = NodoCrear(
                mac=argumentos.mac,
                nombre=argumentos.nombre,
                tanque_id=tanque_id,
                padre_id=padre_id,
            )
            nodo, token = servicio.crear_nodo(sesion, datos)
    except (ValueError, ValidationError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except ErrorDeNegocio as error:
        print(f"Error: {error.message}", file=sys.stderr)
        return 1

    print(f"Nodo {nodo.nombre} creado (id {nodo.id}).")
    if token:
        print(f"Token del autónomo, guárdalo porque no se vuelve a mostrar:\n{token}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
