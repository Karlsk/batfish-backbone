"""Allow durable fault-scenario fork jobs."""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_jobs_kind"), "jobs", type_="check")
    op.create_check_constraint(
        op.f("ck_jobs_kind"),
        "jobs",
        "kind IN ('upload', 'initialization', 'analysis', 'deletion', 'fault_scenario')",
    )


def downgrade():
    op.drop_constraint(op.f("ck_jobs_kind"), "jobs", type_="check")
    op.create_check_constraint(
        op.f("ck_jobs_kind"), "jobs", "kind IN ('upload', 'initialization', 'analysis', 'deletion')"
    )
