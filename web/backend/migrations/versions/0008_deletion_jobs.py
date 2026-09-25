"""Bind resource lifecycle to its current deletion task."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("audit_events", sa.Column("note", sa.String(1000), nullable=True))
    for table in ("networks", "snapshots"):
        op.add_column(table, sa.Column("deletion_job_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_deletion_job_id_jobs"), table, "jobs", ["deletion_job_id"], ["id"]
        )


def downgrade():
    op.drop_column("audit_events", "note")
    for table in ("snapshots", "networks"):
        op.drop_constraint(op.f(f"fk_{table}_deletion_job_id_jobs"), table, type_="foreignkey")
        op.drop_column(table, "deletion_job_id")
