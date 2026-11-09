"""Puente entre el firmware web actual del ESP32 y AquaSense.

El firmware actual es un servidor web: expone `/datos` (JSON con las lecturas), `/abrir` y `/cerrar`
(servo de la tolva). AquaSense espera que el nodo le envíe la telemetría. Este puente corre en la
laptop, en la misma red que el ESP32, y hace de nodo autónomo:

- cada 10 s lee `/datos` y lo manda a `POST /api/v1/device/telemetry`;
- cada 5 s consulta `GET /api/v1/device/config` y ejecuta los comandos: un DISPENSAR de N cargas
  se traduce en N veces `/abrir`, esperar TIEMPO_APERTURA_DISPENSA, `/cerrar`;
- responde cada comando con `POST /api/v1/device/ack` y registra la dosis;
- aplica el modo AUTOMATICO de alimentación, que el firmware no tiene.

Solo usa la biblioteca estándar. Ejemplo:
    python tools/puente_esp32.py --esp32 http://192.168.1.80 --mac 24:6F:28:AB:CD:EF
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field

FIRMWARE = "web-1.0 + puente-1.0"
MODULOS = ["luz", "tds", "flotador", "tolva", "servo"]
# Textos que devuelve el firmware en `ldr_est`, en el mismo orden que la clase 0, 1, 2.
CLASES_DE_LUZ = {"Oscuridad Total": 0, "Luz Tenue": 1, "Luz Brillante": 2}

CADENCIA_TELEMETRIA_S = 10.0
CADENCIA_CONFIG_S = 5.0
TIEMPO_ESPERA_HTTP_S = 8
# Sin una lectura reciente del ESP32 no se piden comandos: no se podrían ejecutar.
VIGENCIA_LECTURA_S = 30.0
MAX_LECTURAS_EN_ESPERA = 360 * 5  # 1 hora de lecturas si se cae el servidor
REINTENTOS_CERRAR = 3
PAUSA_ENTRE_CARGAS_S = 1.0
MS_POR_SEGUNDO = 1000
SEGUNDOS_POR_HORA = 3600

# Valores de fábrica mientras no llegue la configuración del servidor.
PARAMETROS_INICIALES = {
    "MODO_DISPENSA": "MANUAL",
    "INTERVALO_ALIMENTACION_HORAS": 8,
    "CANTIDAD_CARGAS": 1,
    "TIEMPO_APERTURA_DISPENSA": 500,
}


class ErrorDeConexion(Exception):
    """No se pudo hablar con el ESP32 o con el servidor."""


def _ahora_ms() -> int:
    return int(time.time() * MS_POR_SEGUNDO)


def lecturas_desde_datos(datos: dict) -> dict[str, float]:
    """Traduce el JSON de `/datos` a las variables de AquaSense.

    Raises:
        KeyError, ValueError: el JSON no trae el formato esperado.
    """
    valores: dict[str, float] = {
        "nivel_luz_adc": int(datos["ldr"]),
        "tds_ppm": round(float(datos["tds"]), 2),
        # Se usa el veredicto del propio firmware para no contradecir su LED y su buzzer.
        "flotador_bajo": 1 if "BAJO" in str(datos["agua_est"]).upper() else 0,
        "tolva_vacia": 1 if "ALERTA" in str(datos["comida_est"]).upper() else 0,
    }
    clase = CLASES_DE_LUZ.get(str(datos.get("ldr_est", "")))
    if clase is not None:
        valores["luz_clase"] = clase
    distancia = float(datos["dist"])
    if distancia >= 0:  # -1 significa que el ultrasónico no recibió eco
        valores["distancia_tolva_cm"] = round(distancia, 2)
    return valores


def toca_alimentacion_automatica(parametros: dict, ultima: float, ahora: float) -> bool:
    if parametros.get("MODO_DISPENSA") != "AUTOMATICO":
        return False
    intervalo_s = float(parametros.get("INTERVALO_ALIMENTACION_HORAS", 8)) * SEGUNDOS_POR_HORA
    return ahora - ultima >= intervalo_s


class _SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None  # /abrir y /cerrar responden 303: basta con eso, no hace falta cargar la página


class Esp32:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self._abridor = urllib.request.build_opener(_SinRedireccion)

    def datos(self) -> dict:
        try:
            with urllib.request.urlopen(f"{self.url}/datos", timeout=TIEMPO_ESPERA_HTTP_S) as r:  # noqa: S310
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ErrorDeConexion(f"ESP32 sin respuesta en /datos: {error}") from error

    def accionar(self, ruta: str) -> None:
        try:
            self._abridor.open(f"{self.url}{ruta}", timeout=TIEMPO_ESPERA_HTTP_S)
        except urllib.error.HTTPError as error:
            if error.code not in (302, 303):
                raise ErrorDeConexion(f"ESP32 respondió {error.code} en {ruta}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ErrorDeConexion(f"ESP32 sin respuesta en {ruta}: {error}") from error


def dispensar(
    esp32: Esp32,
    cargas: int,
    apertura_ms: int,
    dormir: Callable[[float], None] = time.sleep,
) -> tuple[str, str | None]:
    """Abre y cierra la tolva una vez por carga. Devuelve el resultado y un detalle para el ACK.

    Si una apertura falla se detiene: mejor no dispensar que dar doble ración. Si no logra cerrar,
    lo reintenta antes de reportar la falla, porque la tolva abierta vaciaría el alimento.
    """
    for numero in range(1, cargas + 1):
        try:
            esp32.accionar("/abrir")
        except ErrorDeConexion as error:
            return "fallido", f"No se pudo abrir la tolva en la carga {numero}: {error}"[:200]
        dormir(apertura_ms / MS_POR_SEGUNDO)
        for intento in range(REINTENTOS_CERRAR):
            try:
                esp32.accionar("/cerrar")
                break
            except ErrorDeConexion:
                if intento == REINTENTOS_CERRAR - 1:
                    return "fallido", f"La tolva pudo quedar abierta tras la carga {numero}."
                dormir(PAUSA_ENTRE_CARGAS_S)
        if numero < cargas:
            dormir(PAUSA_ENTRE_CARGAS_S)
    return "confirmado", None


class Servidor:
    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self.token = token

    def _pedir(self, ruta: str, cuerpo: dict | None = None) -> dict:
        peticion = urllib.request.Request(  # noqa: S310 - URL indicada por quien corre el puente
            f"{self.url}/api/v1/device{ruta}",
            data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
            method="POST" if cuerpo is not None else "GET",
            headers={"X-API-Token": self.token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA_HTTP_S) as r:  # noqa: S310
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise PermissionError("El servidor rechazó el token del autónomo.") from error
            raise ErrorDeConexion(f"El servidor respondió {error.code} en {ruta}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ErrorDeConexion(f"Servidor sin respuesta: {error}") from error

    def telemetria(self, lote: dict) -> dict:
        return self._pedir("/telemetry", lote)

    def config(self) -> dict:
        return self._pedir("/config")

    def ack(self, comando_id: int, resultado: str, detalle: str | None) -> None:
        self._pedir("/ack", {"comando_id": comando_id, "resultado": resultado, "detalle": detalle})


@dataclass
class Puente:
    esp32: Esp32
    servidor: Servidor
    mac: str
    boot: int
    parametros: dict = field(default_factory=lambda: dict(PARAMETROS_INICIALES))
    config_version_aplicada: int | None = None
    lote: int = 0
    lecturas_pendientes: list[dict] = field(default_factory=list)
    eventos_pendientes: list[dict] = field(default_factory=list)
    ultima_lectura: float = 0.0
    # Al arrancar se espera un intervalo completo: reiniciar el puente no debe dar otra ración.
    ultima_alimentacion_automatica: float = field(default_factory=time.monotonic)

    def leer_esp32(self) -> bool:
        try:
            valores = lecturas_desde_datos(self.esp32.datos())
        except ErrorDeConexion as error:
            print(error, file=sys.stderr)
            return False
        except (KeyError, ValueError) as error:
            print(f"/datos no trae el formato esperado: {error}", file=sys.stderr)
            return False
        ahora_ms = _ahora_ms()
        self.lecturas_pendientes.extend(
            {"mac": self.mac, "variable": variable, "valor": valor, "boot": self.boot,
             "epoch_ms": ahora_ms, "_medido_ms": ahora_ms}
            for variable, valor in valores.items()
        )  # fmt: skip
        del self.lecturas_pendientes[:-MAX_LECTURAS_EN_ESPERA]
        self.ultima_lectura = time.monotonic()
        return True

    def _para_enviar(self, elemento: dict, ahora_ms: int) -> dict:
        limpio = {k: v for k, v in elemento.items() if not k.startswith("_")}
        limpio["edad_ms"] = max(0, ahora_ms - elemento["_medido_ms"])
        return limpio

    def enviar_telemetria(self) -> None:
        if not self.lecturas_pendientes and not self.eventos_pendientes:
            return
        ahora_ms = _ahora_ms()
        self.lote += 1
        lote = {
            "lote": self.lote,
            "enviado_epoch_ms": ahora_ms,
            "nodos": [
                {"mac": self.mac, "firmware": FIRMWARE, "boot": self.boot, "modulos": MODULOS,
                 "config_version_aplicada": self.config_version_aplicada}
            ],
            "lecturas": [self._para_enviar(x, ahora_ms) for x in self.lecturas_pendientes],
            "eventos": [self._para_enviar(x, ahora_ms) for x in self.eventos_pendientes],
        }  # fmt: skip
        try:
            respuesta = self.servidor.telemetria(lote)
        except ErrorDeConexion as error:
            print(f"{error}; se conservan los datos para reenviarlos.", file=sys.stderr)
            return
        self.lecturas_pendientes.clear()
        self.eventos_pendientes.clear()
        print(
            f"Lote {self.lote}: {respuesta['aceptadas']} aceptadas, "
            f"{respuesta['duplicadas']} duplicadas, {len(respuesta['rechazadas'])} rechazadas"
        )
        for rechazo in respuesta["rechazadas"]:
            print(f"  Rechazo: {rechazo}", file=sys.stderr)

    def _registrar_dosis(self, cargas: int, origen: str, comando_id: int | None) -> None:
        ahora_ms = _ahora_ms()
        self.eventos_pendientes.append(
            {"mac": self.mac, "tipo": "dosis", "cargas": cargas, "origen": origen,
             "comando_id": comando_id, "boot": self.boot, "epoch_ms": ahora_ms,
             "_medido_ms": ahora_ms}
        )  # fmt: skip

    def _ejecutar(self, comando: dict) -> tuple[str, str | None]:
        if comando["mac"] != self.mac:
            return "fallido", "El puente solo controla su propio ESP32."
        if comando["tipo"] != "DISPENSAR":
            return "fallido", "El firmware actual no soporta este comando."
        resultado, detalle = dispensar(
            self.esp32, int(comando["argumento"]), int(self.parametros["TIEMPO_APERTURA_DISPENSA"])
        )
        if resultado == "confirmado":
            self._registrar_dosis(int(comando["argumento"]), "remoto", comando["id"])
        return resultado, detalle

    def consultar_config(self) -> None:
        if time.monotonic() - self.ultima_lectura > VIGENCIA_LECTURA_S:
            return  # El ESP32 no responde: un comando entregado no se podría ejecutar
        try:
            cuerpo = self.servidor.config()
        except ErrorDeConexion as error:
            print(error, file=sys.stderr)
            return
        for nodo in cuerpo["nodos"]:
            if nodo["mac"] == self.mac and nodo["config_version"] != self.config_version_aplicada:
                self.parametros.update(nodo["parametros"])
                self.config_version_aplicada = nodo["config_version"]
                print(f"Configuración v{self.config_version_aplicada} aplicada")
        for comando in cuerpo["comandos"]:
            resultado, detalle = self._ejecutar(comando)
            try:
                self.servidor.ack(comando["id"], resultado, detalle)
            except ErrorDeConexion as error:
                print(
                    f"No se pudo enviar el ACK del comando {comando['id']}: {error}",
                    file=sys.stderr,
                )
            print(f"Comando {comando['id']} {comando['tipo']}: {resultado}")

    def alimentar_si_toca(self) -> None:
        ahora = time.monotonic()
        if not toca_alimentacion_automatica(
            self.parametros, self.ultima_alimentacion_automatica, ahora
        ):
            return
        self.ultima_alimentacion_automatica = ahora
        cargas = int(self.parametros["CANTIDAD_CARGAS"])
        resultado, detalle = dispensar(
            self.esp32, cargas, int(self.parametros["TIEMPO_APERTURA_DISPENSA"])
        )
        if resultado == "confirmado":
            self._registrar_dosis(cargas, "automatico", None)
        print(f"Alimentación automática de {cargas} cargas: {resultado} {detalle or ''}".strip())


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Conecta el firmware web actual del ESP32 con AquaSense."
    )
    parser.add_argument(
        "--servidor",
        default=os.environ.get("PUENTE_SERVIDOR", "http://localhost:8000"),
        help="URL local de AquaSense (o PUENTE_SERVIDOR)",
    )
    esp32 = os.environ.get("PUENTE_ESP32")
    parser.add_argument(
        "--esp32", default=esp32, required=esp32 is None,
        help="URL del ESP32 en la red local, p. ej. http://192.168.1.80 (o PUENTE_ESP32)",
    )  # fmt: skip
    mac = os.environ.get("PUENTE_MAC")
    parser.add_argument(
        "--mac", default=mac, required=mac is None,
        help="MAC con la que se dio de alta el nodo autónomo (o PUENTE_MAC)",
    )  # fmt: skip
    token = os.environ.get("AQUASENSE_TOKEN")
    parser.add_argument(
        "--token", default=token, required=token is None,
        help="token del autónomo; mejor por AQUASENSE_TOKEN, que no queda en el historial",
    )  # fmt: skip
    parser.add_argument("--ciclos", type=int, default=0, help="ciclos de telemetría; 0 = sin fin")
    return parser


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    argumentos = _crear_parser().parse_args()
    puente = Puente(
        esp32=Esp32(argumentos.esp32),
        servidor=Servidor(argumentos.servidor, argumentos.token),
        mac=argumentos.mac.upper(),
        # Cada arranque del puente es un "boot" nuevo para la asignación de hora del servidor.
        boot=int(time.time()) // 60 % 2_000_000_000,
    )
    print(f"Puente: ESP32 {argumentos.esp32} → AquaSense {argumentos.servidor}")
    ciclo = 0
    try:
        while argumentos.ciclos == 0 or ciclo < argumentos.ciclos:
            ciclo += 1
            inicio = time.monotonic()
            puente.leer_esp32()
            puente.enviar_telemetria()
            while time.monotonic() - inicio < CADENCIA_TELEMETRIA_S:
                puente.consultar_config()
                puente.alimentar_si_toca()
                if argumentos.ciclos and ciclo >= argumentos.ciclos:
                    break
                time.sleep(CADENCIA_CONFIG_S)
        puente.enviar_telemetria()  # lo que haya quedado pendiente, como la última dosis
    except PermissionError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
