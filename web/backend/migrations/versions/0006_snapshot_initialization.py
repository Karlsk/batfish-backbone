"""Immutable snapshot input and initialization evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("snapshots", sa.Column("manifest", JSONB()))
    for name in ("initialization_options", "diagnostics"):
        op.add_column(
            "snapshots",
            sa.Column(name, JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        )
    for name in ("engine_version", "sdk_version"):
        op.add_column("snapshots", sa.Column(name, sa.String(128)))


def downgrade():
    for name in (
        "sdk_version",
        "engine_version",
        "diagnostics",
        "initialization_options",
        "manifest",
    ):
        op.drop_column("snapshots", name)
