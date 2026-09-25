"""Persist immutable execution context and retry lineage."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("context", postgresql.JSONB(), nullable=True))
    op.add_column("jobs", sa.Column("retry_of", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_jobs_retry_of_jobs", "jobs", "jobs", ["retry_of"], ["id"])


def downgrade():
    op.drop_constraint("fk_jobs_retry_of_jobs", "jobs", type_="foreignkey")
    op.drop_column("jobs", "retry_of")
    op.drop_column("jobs", "context")
