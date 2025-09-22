"""Add component_twin table.

Revision ID: 8a2f6f9b1cde
Revises: fd531f8868b1
Create Date: 2025-09-22 13:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "8a2f6f9b1cde"
down_revision: str | None = "d37bc4322900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not migration.table_exists("component_twin", conn):
        op.create_table(
            "component_twin",
            sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("flow_id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
            sa.Column("component_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("python_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("python_source", sa.Text(), nullable=True),
            sa.Column("io_schema", sa.JSON(), nullable=True),
            sa.Column("wit_source", sa.Text(), nullable=True),
            sa.Column("rust_source", sa.Text(), nullable=True),
            sa.Column("wasm_blob", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("capability_manifest", sa.JSON(), nullable=True),
            sa.Column("build_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="stale"),
            sa.Column("build_logs_uri", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("last_verified_at", sa.DateTime(), nullable=True),
            sa.Column("determinism_mode", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("parity_metrics", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["flow_id"], ["flow.id"], name="fk_component_twin_flow_id"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("component_twin", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_component_twin_flow_id"), ["flow_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_component_twin_component_id"), ["component_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_component_twin_python_hash"), ["python_hash"], unique=False)
            batch_op.create_index(batch_op.f("ix_component_twin_build_status"), ["build_status"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    if migration.table_exists("component_twin", conn):
        op.drop_table("component_twin")
