"""Network diagnostics and a durable exclusive engine slot."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("networks", sa.Column("sync_error", sa.String(64), nullable=True))
    op.create_table(
        "engine_slot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_engine_slot_singleton")),
        sa.CheckConstraint(
            "state IN ('idle', 'busy', 'unknown')", name=op.f("ck_engine_slot_state")
        ),
    )


def downgrade():
    op.drop_table("engine_slot")
    op.drop_column("networks", "sync_error")
