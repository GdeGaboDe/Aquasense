import pytest

from tools.puente_esp32 import (
    ErrorDeConexion,
    dispensar,
    lecturas_desde_datos,
    toca_alimentacion_automatica,
)

# Lo que devuelve /datos del firmware actual.
DATOS = {
    "ldr": 1500,
    "ldr_est": "Luz Tenue",
    "ldr_col": "#ea580c",
    "tds": 182.45,
    "tds_v": 0.41,
    "agua_est": "NIVEL OK (Tanque Lleno)",
    "agua_col": "#16a34a",
    "dist": 7.25,
    "comida_est": "COMIDA OK",
    "comida_col": "#16a34a",
}


class Esp32Falso:
    def __init__(self, fallar_en: dict[str, int] | None = None) -> None:
        self.llamadas: list[str] = []
        self.fallas = dict(fallar_en or {})

    def accionar(self, ruta: str) -> None:
        self.llamadas.append(ruta)
        if self.fallas.get(ruta, 0) > 0:
            self.fallas[ruta] -= 1
            raise ErrorDeConexion(f"falla en {ruta}")


def test_traduce_el_json_del_firmware_a_variables_de_aquasense():
    assert lecturas_desde_datos(DATOS) == {
        "nivel_luz_adc": 1500,
        "luz_clase": 1,
        "tds_ppm": 182.45,
        "flotador_bajo": 0,
        "tolva_vacia": 0,
        "distancia_tolva_cm": 7.25,
    }


def test_alertas_del_firmware_se_vuelven_booleanos():
    datos = DATOS | {"agua_est": "¡ALERTA! NIVEL BAJO", "comida_est": "¡ALERTA! TOLVA VACÍA"}

    valores = lecturas_desde_datos(datos)

    assert valores["flotador_bajo"] == 1
    assert valores["tolva_vacia"] == 1


def test_sin_eco_del_ultrasonico_no_inventa_una_distancia():
    valores = lecturas_desde_datos(DATOS | {"dist": -1.0, "comida_est": "¡ALERTA! TOLVA VACÍA"})

    assert "distancia_tolva_cm" not in valores
    assert valores["tolva_vacia"] == 1


@pytest.mark.parametrize(
    ("texto", "clase"), [("Oscuridad Total", 0), ("Luz Tenue", 1), ("Luz Brillante", 2)]
)
def test_clase_de_luz_sale_del_estado_del_firmware(texto, clase):
    assert lecturas_desde_datos(DATOS | {"ldr_est": texto})["luz_clase"] == clase


def test_estado_de_luz_desconocido_solo_omite_la_clase():
    assert "luz_clase" not in lecturas_desde_datos(DATOS | {"ldr_est": "Leyendo..."})


def test_json_incompleto_lanza_error():
    with pytest.raises(KeyError):
        lecturas_desde_datos({"ldr": 1})


def test_dispensar_abre_y_cierra_una_vez_por_carga():
    esp32 = Esp32Falso()
    esperas: list[float] = []

    resultado = dispensar(esp32, cargas=2, apertura_ms=600, dormir=esperas.append)

    assert resultado == ("confirmado", None)
    assert esp32.llamadas == ["/abrir", "/cerrar", "/abrir", "/cerrar"]
    assert esperas == [0.6, 1.0, 0.6]


def test_si_falla_una_apertura_se_detiene_sin_dar_mas_cargas():
    esp32 = Esp32Falso(fallar_en={"/abrir": 1})

    resultado, detalle = dispensar(esp32, cargas=3, apertura_ms=500, dormir=lambda _: None)

    assert resultado == "fallido"
    assert "abrir" in detalle
    assert esp32.llamadas == ["/abrir"]


def test_reintenta_cerrar_antes_de_reportar_falla():
    esp32 = Esp32Falso(fallar_en={"/cerrar": 2})

    resultado = dispensar(esp32, cargas=1, apertura_ms=500, dormir=lambda _: None)

    assert resultado == ("confirmado", None)
    assert esp32.llamadas == ["/abrir", "/cerrar", "/cerrar", "/cerrar"]


def test_si_no_logra_cerrar_avisa_que_la_tolva_pudo_quedar_abierta():
    esp32 = Esp32Falso(fallar_en={"/cerrar": 3})

    resultado, detalle = dispensar(esp32, cargas=2, apertura_ms=500, dormir=lambda _: None)

    assert resultado == "fallido"
    assert "abierta" in detalle
    assert esp32.llamadas.count("/abrir") == 1


def test_alimentacion_automatica_solo_en_modo_automatico_y_al_cumplir_el_intervalo():
    automatico = {"MODO_DISPENSA": "AUTOMATICO", "INTERVALO_ALIMENTACION_HORAS": 8}

    assert not toca_alimentacion_automatica({"MODO_DISPENSA": "MANUAL"}, 0, 10**9)
    assert not toca_alimentacion_automatica(automatico, ultima=0, ahora=8 * 3600 - 1)
    assert toca_alimentacion_automatica(automatico, ultima=0, ahora=8 * 3600)
