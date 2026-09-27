"""Persist versioned business traffic concerns."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "business_concerns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("network_id", sa.Uuid(), sa.ForeignKey("networks.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("priority", sa.String(8), nullable=False),
        sa.Column("flows", JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_business_concerns_version"),
        sa.CheckConstraint(
            "priority IN ('high', 'medium', 'low')", name="ck_business_concerns_priority"
        ),
    )
    op.create_index(op.f("ix_business_concerns_network_id"), "business_concerns", ["network_id"])
    op.create_table(
        "business_concern_versions",
        sa.Column("concern_id", sa.Uuid(), sa.ForeignKey("business_concerns.id"), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("network_id", sa.Uuid(), sa.ForeignKey("networks.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("priority", sa.String(8), nullable=False),
        sa.Column("flows", JSONB(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_business_concern_versions_version"),
        sa.CheckConstraint(
            "priority IN ('high', 'medium', 'low')", name="ck_business_concern_versions_priority"
        ),
    )


def downgrade():
    op.drop_table("business_concern_versions")
    op.drop_table("business_concerns")
