"""Catálogos: variable, tipo_alerta y parametro, con sus datos iniciales.

Los datos van escritos aquí y no importados de la app: una migración debe seguir
produciendo lo mismo aunque el código cambie después.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence
from decimal import Decimal as D  # noqa: N817 - hace legibles las tablas de datos

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DECIMAL = sa.Numeric(10, 3)

_VARIABLES = [
    # codigo, nombre, unidad, tipo, min_fisico, max_fisico
    ("temp_c", "Temperatura", "°C", "numero", D("-55"), D("125")),
    ("tds_ppm", "Sólidos disueltos totales", "ppm", "numero", D("0"), D("2000")),
    ("turbidez_ntu", "Turbidez", "NTU", "numero", D("0"), D("3000")),
    ("flotador_bajo", "Nivel de agua bajo", None, "booleano", D("0"), D("1")),
    ("nivel_luz_adc", "Nivel de luz", "ADC", "numero", D("0"), D("4095")),
    ("luz_clase", "Clase de luz", None, "numero", D("0"), D("2")),
    ("distancia_tolva_cm", "Distancia al alimento en la tolva", "cm", "numero", D("0"), D("400")),
    ("tolva_vacia", "Tolva vacía", None, "booleano", D("0"), D("1")),
    ("aireador_encendido", "Aireador encendido", None, "booleano", D("0"), D("1")),
    ("calentador_encendido", "Calentador encendido", None, "booleano", D("0"), D("1")),
    ("alarma_activa", "Alarma activa", None, "booleano", D("0"), D("1")),
]

_TIPOS_ALERTA = [
    # codigo, descripcion, severidad
    ("FUERA_DE_RANGO", "Una variable salió del rango definido para el tanque", "advertencia"),
    ("NIVEL_BAJO", "El nivel de agua del tanque está bajo", "critica"),
    ("TOLVA_VACIA", "La tolva del alimentador está vacía", "advertencia"),
    ("COMANDO_FALLIDO", "Un comando falló o expiró sin ejecutarse", "advertencia"),
]

_PARAMETROS = [
    # codigo, descripcion, tipo, unidad, minimo, maximo, opciones, valor_defecto, modulo_requerido
    ("INTERVALO_ENVIO_S", "Intervalo de envío de telemetría", "entero", "s",
     D("5"), D("60"), None, "10", None),
    ("MODO_DISPENSA", "Modo de alimentación", "opcion", None,
     None, None, ["MANUAL", "AUTOMATICO"], "MANUAL", "servo"),
    ("INTERVALO_ALIMENTACION_HORAS", "Horas entre alimentaciones automáticas", "entero", "h",
     D("1"), D("24"), None, "8", "servo"),
    ("CANTIDAD_CARGAS", "Cargas por alimentación", "entero", None,
     D("1"), D("5"), None, "1", "servo"),
    ("TIEMPO_APERTURA_DISPENSA", "Tiempo de apertura del dispensador", "entero", "ms",
     D("200"), D("2000"), None, "500", "servo"),
    ("ANGULO_REPOSO_SERVO", "Ángulo de reposo del servo", "entero", "°",
     D("0"), D("30"), None, "10", "servo"),
    ("ANGULO_DISPENSA_SERVO", "Ángulo de dispensa del servo", "entero", "°",
     D("45"), D("90"), None, "75", "servo"),
    ("DISTANCIA_TOLVA_VACIA", "Distancia a partir de la cual la tolva está vacía", "decimal", "cm",
     D("5.0"), D("30.0"), None, "15.0", "tolva"),
    ("UMBRAL_LUZ_OSCURIDAD", "Lectura máxima considerada oscuridad", "entero", "ADC",
     D("0"), D("1500"), None, "1000", "luz"),
    ("UMBRAL_LUZ_MODERADA", "Lectura máxima considerada luz moderada", "entero", "ADC",
     D("1501"), D("3000"), None, "2500", "luz"),
    ("COEF_CALIBRACION_TDS", "Coeficiente de calibración del sensor TDS", "decimal", None,
     D("0.80"), D("1.20"), None, "1.00", "tds"),
    ("VOLTAJE_REFERENCIA_ADC", "Voltaje de referencia del ADC", "decimal", "V",
     D("3.20"), D("3.35"), None, "3.30", None),
    ("FRECUENCIA_ALARMA_BUZZER", "Frecuencia del zumbador de alarma", "entero", "Hz",
     D("1000"), D("4000"), None, "2500", "alarma"),
    ("TEMP_ENCENDER_CALENTADOR", "Temperatura para encender el calentador", "decimal", "°C",
     D("18"), D("30"), None, "24.5", "calentador"),
    ("TEMP_APAGAR_CALENTADOR", "Temperatura para apagar el calentador", "decimal", "°C",
     D("18"), D("30"), None, "25.5", "calentador"),
]  # fmt: skip


def upgrade() -> None:
    variable = op.create_table(
        "variable",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(40), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=True),
        sa.Column("tipo", sa.Enum("numero", "booleano", name="tipo_variable"), nullable=False),
        sa.Column("min_fisico", _DECIMAL, nullable=True),
        sa.Column("max_fisico", _DECIMAL, nullable=True),
        sa.CheckConstraint("min_fisico < max_fisico", name=op.f("ck_variable_rango_fisico")),
        sa.UniqueConstraint("codigo", name="uq_variable_codigo"),
    )
    tipo_alerta = op.create_table(
        "tipo_alerta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(40), nullable=False),
        sa.Column("descripcion", sa.String(200), nullable=False),
        sa.Column(
            "severidad", sa.Enum("info", "advertencia", "critica", name="severidad"), nullable=False
        ),
        sa.UniqueConstraint("codigo", name="uq_tipo_alerta_codigo"),
    )
    parametro = op.create_table(
        "parametro",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(40), nullable=False),
        sa.Column("descripcion", sa.String(200), nullable=False),
        sa.Column(
            "tipo", sa.Enum("entero", "decimal", "opcion", name="tipo_parametro"), nullable=False
        ),
        sa.Column("unidad", sa.String(20), nullable=True),
        sa.Column("minimo", _DECIMAL, nullable=True),
        sa.Column("maximo", _DECIMAL, nullable=True),
        sa.Column("opciones", sa.JSON(), nullable=True),
        sa.Column("valor_defecto", sa.String(40), nullable=False),
        sa.Column("modulo_requerido", sa.String(20), nullable=True),
        sa.CheckConstraint("minimo < maximo", name=op.f("ck_parametro_rango")),
        sa.UniqueConstraint("codigo", name="uq_parametro_codigo"),
    )

    op.bulk_insert(
        variable,
        [
            dict(
                zip(
                    ("codigo", "nombre", "unidad", "tipo", "min_fisico", "max_fisico"),
                    fila,
                    strict=True,
                )
            )
            for fila in _VARIABLES
        ],
    )
    op.bulk_insert(
        tipo_alerta,
        [
            dict(zip(("codigo", "descripcion", "severidad"), fila, strict=True))
            for fila in _TIPOS_ALERTA
        ],
    )
    columnas_parametro = (
        "codigo", "descripcion", "tipo", "unidad", "minimo", "maximo",
        "opciones", "valor_defecto", "modulo_requerido",
    )  # fmt: skip
    op.bulk_insert(
        parametro,
        [dict(zip(columnas_parametro, fila, strict=True)) for fila in _PARAMETROS],
    )


def downgrade() -> None:
    op.drop_table("parametro")
    op.drop_table("tipo_alerta")
    op.drop_table("variable")
