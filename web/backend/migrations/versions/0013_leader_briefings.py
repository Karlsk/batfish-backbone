"""Fixed, versioned leader briefings without FKs to deletable source resources."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "briefings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("network_id", sa.Uuid(), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latest_version >= 1", name="ck_briefings_latest_version"),
    )
    op.create_index("ix_briefings_network_id", "briefings", ["network_id"])
    op.create_table(
        "briefing_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_id", sa.Uuid(), sa.ForeignKey("briefings.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("notes", sa.String(4000)),
        sa.Column("frozen", JSONB(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("report_id", "version", name="uq_briefing_report_version"),
        sa.UniqueConstraint("created_by", "idempotency_key", name="uq_briefing_actor_key"),
        sa.CheckConstraint("version >= 1", name="ck_briefing_revisions_version"),
    )
    op.create_index("ix_briefing_revisions_report", "briefing_revisions", ["report_id", "version"])


def downgrade():
    op.drop_table("briefing_revisions")
    op.drop_table("briefings")
