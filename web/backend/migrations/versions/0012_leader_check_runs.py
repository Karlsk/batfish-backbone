"""Persist resumable leader check runs and idempotency reservations."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "check_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("template_version", sa.String(16), nullable=False),
        sa.Column("network_id", sa.Uuid(), sa.ForeignKey("networks.id"), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("snapshots.id"), nullable=False),
        sa.Column("concern_id", sa.Uuid(), sa.ForeignKey("business_concerns.id")),
        sa.Column("concern_version", sa.Integer()),
        sa.Column("frozen_concern", JSONB()),
        sa.Column("snapshot_quality", JSONB(), nullable=False),
        sa.Column("engine_version", sa.String(128), nullable=False),
        sa.Column("sdk_version", sa.String(128), nullable=False),
        sa.Column("effective_parameters", JSONB(), nullable=False),
        sa.Column("job_ids", JSONB(), nullable=False),
        sa.Column("derived_snapshot_id", sa.Uuid(), sa.ForeignKey("snapshots.id")),
        sa.Column("submission_state", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("created_by", "idempotency_key", name="uq_check_runs_actor_key"),
        sa.CheckConstraint(
            "submission_state IN ('submitting','dispatched','succeeded','failed')",
            name="ck_check_runs_submission_state",
        ),
    )
    op.create_index("ix_check_runs_network_created", "check_runs", ["network_id", "created_at"])


def downgrade():
    op.drop_table("check_runs")
