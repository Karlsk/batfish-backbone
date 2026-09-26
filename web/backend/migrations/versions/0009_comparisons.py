"""Persist immutable baseline-to-candidate comparison references."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "comparisons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("network_id", sa.Uuid(), sa.ForeignKey("networks.id"), nullable=False),
        sa.Column("baseline_snapshot_id", sa.Uuid(), sa.ForeignKey("snapshots.id"), nullable=False),
        sa.Column(
            "candidate_snapshot_id", sa.Uuid(), sa.ForeignKey("snapshots.id"), nullable=False
        ),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("baseline_content_hash", sa.String(64), nullable=False),
        sa.Column("candidate_content_hash", sa.String(64), nullable=False),
        sa.Column("baseline_engine_version", sa.String(128), nullable=False),
        sa.Column("candidate_engine_version", sa.String(128), nullable=False),
        sa.Column("baseline_sdk_version", sa.String(128), nullable=False),
        sa.Column("candidate_sdk_version", sa.String(128), nullable=False),
        sa.Column("engine_version", sa.String(128), nullable=False),
        sa.Column("sdk_version", sa.String(128), nullable=False),
        sa.Column("coverage", sa.String(16), nullable=False),
        sa.Column("coverage_notes", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "baseline_snapshot_id <> candidate_snapshot_id",
            name="ck_comparisons_different_snapshots",
        ),
        sa.CheckConstraint("coverage IN ('complete', 'limited')", name="ck_comparisons_coverage"),
    )
    for column in ("network_id", "baseline_snapshot_id", "candidate_snapshot_id"):
        op.create_index(op.f(f"ix_comparisons_{column}"), "comparisons", [column])


def downgrade():
    op.drop_table("comparisons")
