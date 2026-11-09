"""Crea el usuario administrador de la web.

Uso: python -m tools.crear_admin --usuario admin
La contraseña se pide sin mostrarla; también puede llegar por stdin para automatizar.
"""

import argparse
import getpass
import sys
from datetime import UTC, datetime

from app.db import obtener_fabrica_sesiones
from app.servicios.autenticacion import crear_usuario


def _leer_contrasena() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\r\n")
    contrasena = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    if contrasena != getpass.getpass("Repítela: "):
        raise ValueError("Las contraseñas no coinciden.")
    return contrasena


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea el usuario administrador de AquaSense.")
    parser.add_argument("--usuario", required=True, help="nombre del usuario")
    argumentos = parser.parse_args()

    try:
        contrasena = _leer_contrasena()
        with obtener_fabrica_sesiones()() as sesion:
            crear_usuario(sesion, argumentos.usuario, contrasena, datetime.now(UTC))
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Usuario {argumentos.usuario} creado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
