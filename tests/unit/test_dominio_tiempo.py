from datetime import UTC, datetime, timedelta

from app.dominio.tiempo import asignar_hora, redondear_a_ms

RECIBIDO = datetime(2026, 11, 20, 15, 0, 0, tzinfo=UTC)
EPOCH_VALIDO_MS = int((RECIBIDO - timedelta(hours=2)).timestamp() * 1000)


def test_usa_hora_del_servidor_cuando_la_lectura_es_del_boot_actual():
    hora = asignar_hora(RECIBIDO, boot_actual=7, boot_lectura=7, edad_ms=1200, epoch_ms=None)

    assert hora.medido_en == RECIBIDO - timedelta(milliseconds=1200)
    assert hora.origen == "servidor"


def test_prefiere_hora_del_servidor_aunque_traiga_epoch_si_es_del_boot_actual():
    hora = asignar_hora(RECIBIDO, 7, 7, edad_ms=500, epoch_ms=EPOCH_VALIDO_MS)

    assert hora.medido_en == RECIBIDO - timedelta(milliseconds=500)
    assert hora.origen == "servidor"


def test_asigna_hora_ntp_cuando_la_lectura_es_de_un_boot_anterior():
    hora = asignar_hora(RECIBIDO, 7, 6, edad_ms=999, epoch_ms=EPOCH_VALIDO_MS)

    assert hora.medido_en == RECIBIDO - timedelta(hours=2)
    assert hora.origen == "ntp"


def test_marca_desconocida_cuando_es_de_boot_anterior_sin_ntp():
    hora = asignar_hora(RECIBIDO, 7, 6, edad_ms=999, epoch_ms=None)

    assert hora.medido_en == RECIBIDO
    assert hora.origen == "desconocida"


def test_descarta_epoch_mas_de_60_segundos_en_el_futuro():
    futuro_ms = int((RECIBIDO + timedelta(seconds=61)).timestamp() * 1000)

    hora = asignar_hora(RECIBIDO, 7, 6, edad_ms=0, epoch_ms=futuro_ms)

    assert hora.origen == "desconocida"
    assert hora.medido_en == RECIBIDO


def test_acepta_epoch_justo_en_la_tolerancia_de_60_segundos():
    limite_ms = int((RECIBIDO + timedelta(seconds=60)).timestamp() * 1000)

    hora = asignar_hora(RECIBIDO, 7, 6, edad_ms=0, epoch_ms=limite_ms)

    assert hora.origen == "ntp"


def test_descarta_epoch_anterior_a_2026():
    viejo_ms = int(datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC).timestamp() * 1000)

    hora = asignar_hora(RECIBIDO, 7, 6, edad_ms=0, epoch_ms=viejo_ms)

    assert hora.origen == "desconocida"


def test_descarta_epoch_absurdo_sin_fallar():
    hora = asignar_hora(RECIBIDO, 7, 6, edad_ms=0, epoch_ms=10**30)

    assert hora.origen == "desconocida"


def test_sin_boot_anunciado_no_se_considera_boot_actual():
    hora = asignar_hora(RECIBIDO, boot_actual=None, boot_lectura=7, edad_ms=100, epoch_ms=None)

    assert hora.origen == "desconocida"


def test_redondea_a_milisegundos_incluso_al_cruzar_el_segundo():
    momento = datetime(2026, 11, 20, 15, 0, 0, 999_600, tzinfo=UTC)

    assert redondear_a_ms(momento) == datetime(2026, 11, 20, 15, 0, 1, tzinfo=UTC)
