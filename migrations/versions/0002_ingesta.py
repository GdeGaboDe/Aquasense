"""Ingesta: usuarios, tanques, nodos, módulos, sensores, lecturas, comandos, dosis y agua.

`comando` entra aquí porque `dosis.comando_id` lo referencia; su lógica llega en la Fase 2.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FECHA = sa.DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql")


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario", sa.String(60), nullable=False),
        sa.Column("hash_contrasena", sa.String(60), nullable=False),
        sa.Column("sesion_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("creado_en", _FECHA, nullable=False),
        sa.Column("ultimo_acceso", _FECHA, nullable=True),
        sa.UniqueConstraint("usuario", name=op.f("uq_usuario_usuario")),
    )
    op.create_table(
        "tanque",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("volumen_l", sa.Numeric(8, 2), nullable=False),
        sa.Column("especie", sa.String(80), nullable=True),
        sa.Column("notas", sa.String(500), nullable=True),
        sa.CheckConstraint("volumen_l > 0", name=op.f("ck_tanque_volumen_positivo")),
        sa.UniqueConstraint("nombre", name=op.f("uq_tanque_nombre")),
    )
    op.create_table(
        "nodo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mac", sa.String(17), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("tanque_id", sa.Integer(), nullable=False),
        sa.Column("padre_id", sa.Integer(), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("firmware", sa.String(20), nullable=True),
        sa.Column("boot_actual", sa.Integer(), nullable=True),
        sa.Column("config_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("config_version_aplicada", sa.Integer(), nullable=True),
        sa.Column("ultimo_contacto", _FECHA, nullable=True),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "(padre_id IS NULL AND token_hash IS NOT NULL) "
            "OR (padre_id IS NOT NULL AND token_hash IS NULL)",
            name=op.f("ck_nodo_token_solo_en_autonomo"),
        ),
        sa.ForeignKeyConstraint(
            ["tanque_id"], ["tanque.id"], name=op.f("fk_nodo_tanque_id_tanque")
        ),
        sa.ForeignKeyConstraint(["padre_id"], ["nodo.id"], name=op.f("fk_nodo_padre_id_nodo")),
        sa.UniqueConstraint("mac", name=op.f("uq_nodo_mac")),
        sa.UniqueConstraint("tanque_id", name=op.f("uq_nodo_tanque_id")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_nodo_token_hash")),
    )
    op.create_table(
        "nodo_modulo",
        sa.Column("nodo_id", sa.Integer(), nullable=False),
        sa.Column("modulo", sa.String(20), nullable=False),
        sa.Column("detectado_en", _FECHA, nullable=False),
        sa.PrimaryKeyConstraint("nodo_id", "modulo", name=op.f("pk_nodo_modulo")),
        sa.ForeignKeyConstraint(["nodo_id"], ["nodo.id"], name=op.f("fk_nodo_modulo_nodo_id_nodo")),
    )
    op.create_table(
        "sensor",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nodo_id", sa.Integer(), nullable=False),
        sa.Column("variable_id", sa.Integer(), nullable=False),
        sa.Column("detectado_en", _FECHA, nullable=False),
        sa.Column("ultimo_visto", _FECHA, nullable=False),
        sa.ForeignKeyConstraint(["nodo_id"], ["nodo.id"], name=op.f("fk_sensor_nodo_id_nodo")),
        sa.ForeignKeyConstraint(
            ["variable_id"], ["variable.id"], name=op.f("fk_sensor_variable_id_variable")
        ),
        sa.UniqueConstraint("nodo_id", "variable_id", name=op.f("uq_sensor_nodo_id_variable_id")),
    )
    op.create_table(
        "lectura",
        sa.Column("sensor_id", sa.Integer(), nullable=False),
        sa.Column("medido_en", _FECHA, nullable=False),
        sa.Column("valor", sa.Numeric(10, 3), nullable=False),
        sa.Column("recibido_en", _FECHA, nullable=False),
        sa.Column(
            "origen_hora",
            sa.Enum("servidor", "ntp", "desconocida", name="origen_hora"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("sensor_id", "medido_en", name=op.f("pk_lectura")),
        sa.ForeignKeyConstraint(
            ["sensor_id"], ["sensor.id"], name=op.f("fk_lectura_sensor_id_sensor")
        ),
    )
    op.create_table(
        "comando",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nodo_id", sa.Integer(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum("DISPENSAR", "SILENCIAR_ALARMA", "AIREADOR", name="tipo_comando"),
            nullable=False,
        ),
        sa.Column("argumento", sa.Integer(), nullable=True),
        sa.Column(
            "estado",
            sa.Enum(
                "pendiente", "entregado", "confirmado", "fallido", "expirado", name="estado_comando"
            ),
            nullable=False,
        ),
        sa.Column("creado_por", sa.Integer(), nullable=False),
        sa.Column("creado_en", _FECHA, nullable=False),
        sa.Column("expira_en", _FECHA, nullable=False),
        sa.Column("entregado_en", _FECHA, nullable=True),
        sa.Column("resuelto_en", _FECHA, nullable=True),
        sa.Column("detalle", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(["nodo_id"], ["nodo.id"], name=op.f("fk_comando_nodo_id_nodo")),
        sa.ForeignKeyConstraint(
            ["creado_por"], ["usuario.id"], name=op.f("fk_comando_creado_por_usuario")
        ),
    )
    op.create_index(op.f("ix_comando_nodo_id_estado"), "comando", ["nodo_id", "estado"])
    op.create_table(
        "dosis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nodo_id", sa.Integer(), nullable=False),
        sa.Column("cargas", sa.Integer(), nullable=False),
        sa.Column(
            "origen", sa.Enum("remoto", "automatico", "local", name="origen_dosis"), nullable=False
        ),
        sa.Column("dosificada_en", _FECHA, nullable=False),
        sa.Column("comando_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("cargas > 0", name=op.f("ck_dosis_cargas_positivas")),
        sa.ForeignKeyConstraint(["nodo_id"], ["nodo.id"], name=op.f("fk_dosis_nodo_id_nodo")),
        sa.ForeignKeyConstraint(
            ["comando_id"], ["comando.id"], name=op.f("fk_dosis_comando_id_comando")
        ),
        sa.UniqueConstraint(
            "nodo_id", "dosificada_en", name=op.f("uq_dosis_nodo_id_dosificada_en")
        ),
        sa.UniqueConstraint("comando_id", name=op.f("uq_dosis_comando_id")),
    )
    op.create_table(
        "cambio_agua",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tanque_id", sa.Integer(), nullable=False),
        sa.Column("realizado_en", _FECHA, nullable=False),
        sa.Column("porcentaje", sa.Numeric(5, 2), nullable=False),
        sa.Column("registrado_por", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "porcentaje > 0 AND porcentaje <= 100", name=op.f("ck_cambio_agua_porcentaje_valido")
        ),
        sa.ForeignKeyConstraint(
            ["tanque_id"], ["tanque.id"], name=op.f("fk_cambio_agua_tanque_id_tanque")
        ),
        sa.ForeignKeyConstraint(
            ["registrado_por"], ["usuario.id"], name=op.f("fk_cambio_agua_registrado_por_usuario")
        ),
    )


def downgrade() -> None:
    op.drop_table("cambio_agua")
    op.drop_table("dosis")
    op.drop_table("comando")
    op.drop_table("lectura")
    op.drop_table("sensor")
    op.drop_table("nodo_modulo")
    op.drop_table("nodo")
    op.drop_table("tanque")
    op.drop_table("usuario")
