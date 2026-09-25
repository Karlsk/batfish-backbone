"""Versioned immutable result cache."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("results", sa.Column("cache_key", sa.String(64)))
    op.create_unique_constraint(op.f("uq_results_cache_key"), "results", ["cache_key"])


def downgrade():
    op.drop_constraint(op.f("uq_results_cache_key"), "results", type_="unique")
    op.drop_column("results", "cache_key")
