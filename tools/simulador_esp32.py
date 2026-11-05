"""Simula un nodo autónomo con N satélites, sin hardware (CLAUDE.md, sección 12).

Solo usa la biblioteca estándar y no importa nada de `app`: habla con el servidor por HTTP,
igual que el ESP32.

Ejemplo:
    python tools/simulador_esp32.py --url http://localhost:8000 --token TOKEN \
        --mac 24:6F:28:AB:CD:EF --satelite 24:6F:28:11:22:33=temp,turbidez,flotador,alarma
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

CADENCIA_TELEMETRIA_S = 10.0
CADENCIA_CONFIG_S = 5.0
TIEMPO_ESPERA_HTTP_S = 10
MS_POR_SEGUNDO = 1000
MODULOS_AUTONOMO = "temp,tds,turbidez,flotador,luz,tolva,servo,aireador,alarma"
FIRMWARE = "sim-1.0"

# Sube poco a poco para que la predicción del cambio de agua tenga una tendencia que estimar.
TDS_INICIAL_PPM = 150.0
TDS_AUMENTO_POR_LECTURA_PPM = 0.02
PROBABILIDAD_ALERTA = 0.02
PROBABILIDAD_DOSIS = 0.01

_ALEATORIO = random.Random()  # noqa: S311 - son datos simulados, no un uso criptográfico


@dataclass
class Nodo:
    mac: str
    modulos: list[str]
    tds_ppm: float = TDS_INICIAL_PPM


@dataclass
class Estado:
    autonomo: Nodo
    satelites: list[Nodo]
    boot: int = 1
    lote: int = 0
    pendientes_lecturas: list[dict] = field(default_factory=list)
    pendientes_eventos: list[dict] = field(default_factory=list)
    config_no_disponible_avisado: bool = False

    @property
    def nodos(self) -> list[Nodo]:
        return [self.autonomo, *self.satelites]


def _caso_raro(probabilidad: float) -> bool:
    return _ALEATORIO.random() < probabilidad


def _valores_de_modulo(modulo: str, nodo: Nodo) -> dict[str, float]:
    if modulo == "temp":
        temperatura = 34.0 if _caso_raro(PROBABILIDAD_ALERTA) else _ALEATORIO.uniform(24.5, 26.0)
        return {"temp_c": round(temperatura, 2)}
    if modulo == "tds":
        nodo.tds_ppm += TDS_AUMENTO_POR_LECTURA_PPM
        return {"tds_ppm": round(nodo.tds_ppm + _ALEATORIO.uniform(-1, 1), 1)}
    if modulo == "turbidez":
        return {"turbidez_ntu": round(_ALEATORIO.uniform(1, 8), 1)}
    if modulo == "flotador":
        return {"flotador_bajo": 1 if _caso_raro(PROBABILIDAD_ALERTA) else 0}
    if modulo == "luz":
        nivel = _ALEATORIO.randint(800, 2800)
        clase = 0 if nivel < 1000 else 1 if nivel < 2500 else 2
        return {"nivel_luz_adc": nivel, "luz_clase": clase}
    if modulo == "tolva":
        vacia = _caso_raro(PROBABILIDAD_ALERTA)
        return {
            "distancia_tolva_cm": 20.0 if vacia else round(_ALEATORIO.uniform(3, 10), 1),
            "tolva_vacia": 1 if vacia else 0,
        }
    if modulo in ("aireador", "calentador", "alarma"):
        codigo = {"aireador": "aireador_encendido", "calentador": "calentador_encendido"}
        return {codigo.get(modulo, "alarma_activa"): 1 if modulo == "aireador" else 0}
    return {}  # servo y rtc no reportan variables


def _medir(estado: Estado) -> None:
    """Toma una lectura de cada módulo y la deja pendiente de enviar."""
    ahora_ms = int(time.time() * MS_POR_SEGUNDO)
    for nodo in estado.nodos:
        for modulo in nodo.modulos:
            for variable, valor in _valores_de_modulo(modulo, nodo).items():
                estado.pendientes_lecturas.append(
                    {
                        "mac": nodo.mac,
                        "variable": variable,
                        "valor": valor,
                        "boot": estado.boot,
                        "epoch_ms": ahora_ms,
                        "_medido_ms": ahora_ms,
                    }
                )
        if "servo" in nodo.modulos and _caso_raro(PROBABILIDAD_DOSIS):
            estado.pendientes_eventos.append(
                {
                    "mac": nodo.mac,
                    "tipo": "dosis",
                    "cargas": _ALEATORIO.randint(1, 3),
                    "origen": "automatico",
                    "comando_id": None,
                    "boot": estado.boot,
                    "epoch_ms": ahora_ms,
                    "_medido_ms": ahora_ms,
                }
            )


def _para_enviar(elemento: dict, ahora_ms: int) -> dict:
    """Calcula `edad_ms` al momento de enviar y quita el dato interno del simulador."""
    limpio = {clave: valor for clave, valor in elemento.items() if not clave.startswith("_")}
    limpio["edad_ms"] = max(0, ahora_ms - elemento["_medido_ms"])
    return limpio


def construir_lote(estado: Estado) -> dict:
    ahora_ms = int(time.time() * MS_POR_SEGUNDO)
    estado.lote += 1
    return {
        "lote": estado.lote,
        "enviado_epoch_ms": ahora_ms,
        "nodos": [
            {
                "mac": nodo.mac,
                "firmware": FIRMWARE,
                "boot": estado.boot,
                "modulos": nodo.modulos,
                "config_version_aplicada": 1,
            }
            for nodo in estado.nodos
        ],
        "lecturas": [_para_enviar(x, ahora_ms) for x in estado.pendientes_lecturas],
        "eventos": [_para_enviar(x, ahora_ms) for x in estado.pendientes_eventos],
    }


def _peticion(url: str, token: str, cuerpo: dict | None = None) -> tuple[int, dict | None]:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(  # noqa: S310 - la URL la indica quien corre el simulador
        url,
        data=datos,
        method="POST" if datos else "GET",
        headers={"X-API-Token": token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA_HTTP_S) as respuesta:  # noqa: S310
            return respuesta.status, json.loads(respuesta.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, None


def enviar_telemetria(url_base: str, token: str, estado: Estado) -> bool:
    """Envía lo pendiente. Devuelve False si hubo que conservarlo para reintentar."""
    lote = construir_lote(estado)
    try:
        codigo, cuerpo = _peticion(f"{url_base}/api/v1/device/telemetry", token, lote)
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"Sin conexión ({error}); se conservan las lecturas.", file=sys.stderr)
        return False
    if codigo == 401:
        raise PermissionError("El servidor rechazó el token.")
    if codigo != 200 or cuerpo is None:
        print(f"Telemetría respondió {codigo}; se conservan las lecturas.", file=sys.stderr)
        return False
    estado.pendientes_lecturas.clear()
    estado.pendientes_eventos.clear()
    print(
        f"Lote {lote['lote']}: {cuerpo['aceptadas']} aceptadas, "
        f"{cuerpo['duplicadas']} duplicadas, {len(cuerpo['rechazadas'])} rechazadas"
    )
    for rechazo in cuerpo["rechazadas"]:
        print(f"  Rechazo: {rechazo}", file=sys.stderr)
    return True


def consultar_config(url_base: str, token: str, estado: Estado) -> None:
    try:
        codigo, _ = _peticion(f"{url_base}/api/v1/device/config", token)
    except (urllib.error.URLError, TimeoutError):
        return
    # /device/config llega en la Fase 2: hasta entonces solo se avisa una vez.
    if codigo == 404 and not estado.config_no_disponible_avisado:
        print("El servidor aún no ofrece /device/config.", file=sys.stderr)
        estado.config_no_disponible_avisado = True


def _leer_satelite(texto: str) -> Nodo:
    mac, separador, modulos = texto.partition("=")
    if not separador or not modulos:
        raise argparse.ArgumentTypeError("usa el formato MAC=modulo,modulo")
    return Nodo(mac=mac, modulos=modulos.split(","))


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simula un ESP32 autónomo con sus satélites.")
    parser.add_argument("--url", default="http://localhost:8000", help="URL local del servidor")
    token = os.environ.get("AQUASENSE_TOKEN")
    parser.add_argument(
        "--token",
        default=token,
        required=token is None,
        help="token del autónomo; o la variable AQUASENSE_TOKEN, que no queda en el historial",
    )
    parser.add_argument("--mac", required=True, help="MAC del autónomo")
    parser.add_argument("--modulos", default=MODULOS_AUTONOMO, help="módulos del autónomo")
    parser.add_argument(
        "--satelite",
        action="append",
        type=_leer_satelite,
        default=[],
        metavar="MAC=mod,mod",
        help="satélite con sus módulos; se puede repetir",
    )
    parser.add_argument(
        "--ciclos", type=int, default=0, help="ciclos de telemetría a enviar; 0 = sin límite"
    )
    parser.add_argument(
        "--intervalo", type=float, default=CADENCIA_TELEMETRIA_S, help="segundos entre lecturas"
    )
    parser.add_argument(
        "--sin-red",
        type=int,
        default=0,
        metavar="CICLOS",
        help="acumula esa cantidad de ciclos sin enviar y luego los reenvía en lote",
    )
    parser.add_argument(
        "--reinicio",
        action="store_true",
        help="cambia boot antes del primer envío, como si hubiera reiniciado sin red",
    )
    parser.add_argument("--boot", type=int, default=1, help="contador de arranques inicial")
    return parser


def _pausar_y_consultar(url: str, token: str, estado: Estado, intervalo: float) -> None:
    """Espera hasta la siguiente lectura y consulta la configuración con su propia cadencia."""
    fin = time.monotonic() + intervalo
    while (restante := fin - time.monotonic()) > 0:
        time.sleep(min(restante, CADENCIA_CONFIG_S))
        consultar_config(url, token, estado)


def ejecutar(argumentos: argparse.Namespace) -> int:
    url = argumentos.url.rstrip("/")
    estado = Estado(
        autonomo=Nodo(mac=argumentos.mac, modulos=argumentos.modulos.split(",")),
        satelites=argumentos.satelite,
        boot=argumentos.boot,
    )
    ciclos_sin_red = argumentos.sin_red
    ciclo = 0
    while argumentos.ciclos == 0 or ciclo < argumentos.ciclos:
        ciclo += 1
        _medir(estado)
        if ciclo <= ciclos_sin_red:
            print(f"Sin red: {len(estado.pendientes_lecturas)} lecturas acumuladas")
        else:
            if argumentos.reinicio:
                estado.boot += 1
                argumentos.reinicio = False
                print(f"Reinicio simulado: boot {estado.boot}")
            enviar_telemetria(url, argumentos.token, estado)
        if argumentos.ciclos == 0 or ciclo < argumentos.ciclos:
            _pausar_y_consultar(url, argumentos.token, estado, argumentos.intervalo)
    return 1 if estado.pendientes_lecturas else 0


def main() -> int:
    argumentos = _crear_parser().parse_args()
    try:
        return ejecutar(argumentos)
    except PermissionError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
