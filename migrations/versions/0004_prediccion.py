"""Predicción del cambio de agua.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FECHA = sa.DateTime().with_variant(mysql.DATETIME(fsp=3), "mysql")


def upgrade() -> None:
    op.create_table(
        "prediccion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cambio_agua_id", sa.Integer(), nullable=False),
        sa.Column("generada_en", _FECHA, nullable=False),
        sa.Column("modelo_version", sa.String(20), nullable=False),
        sa.Column("pendiente", sa.Numeric(14, 6), nullable=False),
        sa.Column("intercepto", sa.Numeric(14, 6), nullable=False),
        sa.Column("limite_tds", sa.Numeric(10, 3), nullable=False),
        sa.Column("r2", sa.Numeric(7, 6), nullable=True),
        sa.Column("n_muestras", sa.Integer(), nullable=False),
        sa.Column("baseline_dias", sa.Numeric(8, 3), nullable=True),
        sa.ForeignKeyConstraint(
            ["cambio_agua_id"],
            ["cambio_agua.id"],
            name=op.f("fk_prediccion_cambio_agua_id_cambio_agua"),
        ),
        sa.CheckConstraint("n_muestras > 0", name=op.f("ck_prediccion_muestras_positivas")),
    )
    op.create_index(
        op.f("ix_prediccion_cambio_agua_id_generada_en"),
        "prediccion",
        ["cambio_agua_id", "generada_en"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_prediccion_cambio_agua_id_generada_en"), table_name="prediccion")
    op.drop_table("prediccion")
