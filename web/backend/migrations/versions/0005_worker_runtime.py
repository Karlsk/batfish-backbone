"""Independent worker observations and administrator reconciliation evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "worker_status",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("worker_id", sa.String(128), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("engine_checked_at", sa.DateTime(timezone=True)),
        sa.Column("engine_available", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_table(
        "engine_reconciliations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resolution", sa.String(32), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade():
    op.drop_table("engine_reconciliations")
    op.drop_table("worker_status")
