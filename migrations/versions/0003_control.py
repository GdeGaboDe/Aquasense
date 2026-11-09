"""Control: umbrales, alertas y valores de parámetros por nodo.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FECHA = sa.DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql")
_DECIMAL = sa.Numeric(10, 3)


def upgrade() -> None:
    op.create_table(
        "umbral",
        sa.Column("tanque_id", sa.Integer(), nullable=False),
        sa.Column("variable_id", sa.Integer(), nullable=False),
        sa.Column("minimo", _DECIMAL, nullable=True),
        sa.Column("maximo", _DECIMAL, nullable=True),
        sa.Column("histeresis", _DECIMAL, nullable=False),
        sa.PrimaryKeyConstraint("tanque_id", "variable_id", name=op.f("pk_umbral")),
        sa.ForeignKeyConstraint(
            ["tanque_id"], ["tanque.id"], name=op.f("fk_umbral_tanque_id_tanque")
        ),
        sa.ForeignKeyConstraint(
            ["variable_id"], ["variable.id"], name=op.f("fk_umbral_variable_id_variable")
        ),
        sa.CheckConstraint("minimo < maximo", name=op.f("ck_umbral_rango")),
        sa.CheckConstraint("histeresis >= 0", name=op.f("ck_umbral_histeresis_no_negativa")),
    )
    op.create_table(
        "alerta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tanque_id", sa.Integer(), nullable=False),
        sa.Column("nodo_id", sa.Integer(), nullable=True),
        sa.Column("tipo_alerta_id", sa.Integer(), nullable=False),
        sa.Column("variable_id", sa.Integer(), nullable=True),
        sa.Column("valor", _DECIMAL, nullable=True),
        sa.Column("iniciada_en", _FECHA, nullable=False),
        sa.Column("resuelta_en", _FECHA, nullable=True),
        sa.Column("variable_clave", sa.Integer(), sa.Computed("coalesce(variable_id, 0)")),
        sa.Column("activa", sa.Integer(), sa.Computed("CASE WHEN resuelta_en IS NULL THEN 1 END")),
        sa.ForeignKeyConstraint(
            ["tanque_id"], ["tanque.id"], name=op.f("fk_alerta_tanque_id_tanque")
        ),
        sa.ForeignKeyConstraint(["nodo_id"], ["nodo.id"], name=op.f("fk_alerta_nodo_id_nodo")),
        sa.ForeignKeyConstraint(
            ["tipo_alerta_id"],
            ["tipo_alerta.id"],
            name=op.f("fk_alerta_tipo_alerta_id_tipo_alerta"),
        ),
        sa.ForeignKeyConstraint(
            ["variable_id"], ["variable.id"], name=op.f("fk_alerta_variable_id_variable")
        ),
        sa.UniqueConstraint(
            "tanque_id",
            "tipo_alerta_id",
            "variable_clave",
            "activa",
            name=op.f("uq_alerta_tanque_id_tipo_alerta_id_variable_clave_activa"),
        ),
    )
    op.create_index(op.f("ix_alerta_tanque_id_resuelta_en"), "alerta", ["tanque_id", "resuelta_en"])
    op.create_table(
        "valor_parametro",
        sa.Column("nodo_id", sa.Integer(), nullable=False),
        sa.Column("parametro_id", sa.Integer(), nullable=False),
        sa.Column("valor", sa.String(40), nullable=False),
        sa.Column("modificado_en", _FECHA, nullable=False),
        sa.Column("modificado_por", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("nodo_id", "parametro_id", name=op.f("pk_valor_parametro")),
        sa.ForeignKeyConstraint(
            ["nodo_id"], ["nodo.id"], name=op.f("fk_valor_parametro_nodo_id_nodo")
        ),
        sa.ForeignKeyConstraint(
            ["parametro_id"],
            ["parametro.id"],
            name=op.f("fk_valor_parametro_parametro_id_parametro"),
        ),
        sa.ForeignKeyConstraint(
            ["modificado_por"],
            ["usuario.id"],
            name=op.f("fk_valor_parametro_modificado_por_usuario"),
        ),
    )


def downgrade() -> None:
    op.drop_table("valor_parametro")
    # Sin drop_index previo: MySQL lo rechaza porque la llave foránea de tanque_id usa el índice.
    op.drop_table("alerta")
    op.drop_table("umbral")
