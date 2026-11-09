import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.modelos import Base, Parametro, TipoAlerta, Variable


def test_modelos_y_migraciones_no_tienen_diferencias(engine: Engine):
    with engine.connect() as conexion:
        contexto = MigrationContext.configure(conexion)

        diferencias = compare_metadata(contexto, Base.metadata)

    assert diferencias == []


def test_restricciones_check_conservan_el_nombre_de_la_convencion(engine: Engine):
    inspector = inspect(engine)

    nombres = {
        restriccion["name"]
        for tabla in inspector.get_table_names()
        for restriccion in inspector.get_check_constraints(tabla)
    }

    assert nombres == {
        "ck_variable_rango_fisico",
        "ck_parametro_rango",
        "ck_tanque_volumen_positivo",
        "ck_nodo_token_solo_en_autonomo",
        "ck_dosis_cargas_positivas",
        "ck_cambio_agua_porcentaje_valido",
        "ck_umbral_rango",
        "ck_umbral_histeresis_no_negativa",
        "ck_prediccion_muestras_positivas",
    }


def test_la_migracion_se_puede_revertir_sin_dejar_tablas(engine: Engine, alembic_config: Config):
    command.downgrade(alembic_config, "base")
    try:
        tablas = set(inspect(engine).get_table_names())
    finally:
        command.upgrade(alembic_config, "head")

    assert tablas <= {"alembic_version"}


def test_catalogo_de_variables_trae_las_once_de_los_modulos(engine: Engine):
    with Session(engine) as sesion:
        codigos = set(sesion.scalars(select(Variable.codigo)))

    assert codigos == {
        "temp_c",
        "tds_ppm",
        "turbidez_ntu",
        "flotador_bajo",
        "nivel_luz_adc",
        "luz_clase",
        "distancia_tolva_cm",
        "tolva_vacia",
        "aireador_encendido",
        "calentador_encendido",
        "alarma_activa",
    }


def test_unidad_con_acento_se_guarda_sin_corromperse(engine: Engine):
    with Session(engine) as sesion:
        variable = sesion.scalar(select(Variable).where(Variable.codigo == "temp_c"))

    assert variable is not None
    assert variable.unidad == "°C"
    assert variable.tipo == "numero"


def test_catalogo_de_alertas_trae_los_tipos_con_su_severidad(engine: Engine):
    with Session(engine) as sesion:
        tipos = {t.codigo: t.severidad.value for t in sesion.scalars(select(TipoAlerta))}

    assert tipos == {
        "FUERA_DE_RANGO": "advertencia",
        "NIVEL_BAJO": "critica",
        "TOLVA_VACIA": "advertencia",
        "COMANDO_FALLIDO": "advertencia",
    }


def test_catalogo_de_parametros_coincide_con_la_tabla_del_documento(engine: Engine):
    with Session(engine) as sesion:
        parametros = {p.codigo: p for p in sesion.scalars(select(Parametro))}

    assert len(parametros) == 15
    modo = parametros["MODO_DISPENSA"]
    assert modo.opciones == ["MANUAL", "AUTOMATICO"]
    assert modo.valor_defecto == "MANUAL"
    assert modo.modulo_requerido == "servo"
    voltaje = parametros["VOLTAJE_REFERENCIA_ADC"]
    assert (str(voltaje.minimo), str(voltaje.maximo)) == ("3.200", "3.350")
    assert voltaje.modulo_requerido is None


def test_cada_parametro_tiene_un_defecto_dentro_de_su_rango(engine: Engine):
    with Session(engine) as sesion:
        parametros = list(sesion.scalars(select(Parametro)))

    for parametro in parametros:
        if parametro.opciones is not None:
            assert parametro.valor_defecto in parametro.opciones
        else:
            assert parametro.minimo <= float(parametro.valor_defecto) <= parametro.maximo


def test_la_base_rechaza_un_rango_fisico_invertido(engine: Engine):
    sentencia = text(
        "INSERT INTO variable (codigo, nombre, tipo, min_fisico, max_fisico) "
        "VALUES ('x', 'x', 'numero', 10, 5)"
    )

    with engine.connect() as conexion, pytest.raises(DBAPIError):
        conexion.execute(sentencia)
