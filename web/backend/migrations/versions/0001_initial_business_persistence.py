"""initial business persistence"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "must_change_password", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('admin', 'member')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_audit_events_actor_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("csrf_secret", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_sessions_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    op.create_index(
        op.f("ix_auth_sessions_expires_at"), "auth_sessions", ["expires_at"], unique=False
    )
    op.create_table(
        "networks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("engine_name", sa.String(length=128), nullable=False),
        sa.Column("sync_state", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sync_state IN ('pending', 'ready', 'failed', 'deleting', 'deleted')",
            name=op.f("ck_networks_sync_state"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_networks_created_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_networks")),
        sa.UniqueConstraint("engine_name", name=op.f("uq_networks_engine_name")),
    )
    op.create_table(
        "snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("network_id", sa.Uuid(), nullable=False),
        sa.Column("engine_name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("initialization_job_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column(
            "quality_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("base_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'initializing', 'ready', 'ready_with_warnings', 'failed', 'deleting', 'deleted')",
            name=op.f("ck_snapshots_status"),
        ),
        sa.ForeignKeyConstraint(
            ["base_snapshot_id"],
            ["snapshots.id"],
            name=op.f("fk_snapshots_base_snapshot_id_snapshots"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_snapshots_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["network_id"], ["networks.id"], name=op.f("fk_snapshots_network_id_networks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_snapshots")),
        sa.UniqueConstraint("engine_name", name=op.f("uq_snapshots_engine_name")),
    )
    op.create_index(op.f("ix_snapshots_network_id"), "snapshots", ["network_id"], unique=False)
    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("network_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["network_id"], ["networks.id"], name=op.f("fk_uploads_network_id_networks")
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_uploads_owner_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploads")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_uploads_storage_key")),
    )
    op.create_index(op.f("ix_uploads_expires_at"), "uploads", ["expires_at"], unique=False)
    op.create_index(op.f("ix_uploads_network_id"), "uploads", ["network_id"], unique=False)
    op.create_table(
        "results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("network_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("reference_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("coverage", sa.String(length=16), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("truncation_reason", sa.String(length=512), nullable=True),
        sa.Column("storage_key", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "coverage IN ('complete', 'limited', 'unknown')", name=op.f("ck_results_coverage")
        ),
        sa.CheckConstraint(
            "kind IN ('table', 'traces', 'graph', 'diff')", name=op.f("ck_results_kind")
        ),
        sa.CheckConstraint(
            "NOT truncated OR length(truncation_reason) > 0 AND truncation_reason IS NOT NULL",
            name=op.f("ck_results_truncation_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["network_id"], ["networks.id"], name=op.f("fk_results_network_id_networks")
        ),
        sa.ForeignKeyConstraint(
            ["reference_snapshot_id"],
            ["snapshots.id"],
            name=op.f("fk_results_reference_snapshot_id_snapshots"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshots.id"], name=op.f("fk_results_snapshot_id_snapshots")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_results")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_results_storage_key")),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("network_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("resource_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requested_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effective_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column("phase", sa.String(length=128), server_default="queued", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engine_state", sa.String(length=16), server_default="idle", nullable=False),
        sa.Column("cancel_allowed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("result_id", sa.Uuid(), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "engine_state IN ('idle', 'busy', 'unknown')", name=op.f("ck_jobs_engine_state")
        ),
        sa.CheckConstraint(
            "kind IN ('upload', 'initialization', 'analysis', 'deletion')",
            name=op.f("ck_jobs_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted')",
            name=op.f("ck_jobs_status"),
        ),
        sa.CheckConstraint("attempt >= 0", name=op.f("ck_jobs_attempt")),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_jobs_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["network_id"], ["networks.id"], name=op.f("fk_jobs_network_id_networks")
        ),
        sa.ForeignKeyConstraint(
            ["result_id"], ["results.id"], name=op.f("fk_jobs_result_id_results")
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshots.id"], name=op.f("fk_jobs_snapshot_id_snapshots")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index(op.f("ix_jobs_network_id"), "jobs", ["network_id"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("route", sa.String(length=255), nullable=False),
        sa.Column("resource_key", sa.String(length=128), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_idempotency_records_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_idempotency_records_job_id_jobs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_records")),
        sa.UniqueConstraint(
            "actor_id", "route", "resource_key", "key", name="uq_idempotency_scope"
        ),
    )
    op.create_index(
        op.f("ix_idempotency_records_expires_at"),
        "idempotency_records",
        ["expires_at"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_snapshots_initialization_job_id_jobs",
        "snapshots",
        "jobs",
        ["initialization_job_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_snapshots_initialization_job_id_jobs", "snapshots", type_="foreignkey")
    op.drop_index(op.f("ix_idempotency_records_expires_at"), table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_network_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("results")
    op.drop_index(op.f("ix_uploads_network_id"), table_name="uploads")
    op.drop_index(op.f("ix_uploads_expires_at"), table_name="uploads")
    op.drop_table("uploads")
    op.drop_index(op.f("ix_snapshots_network_id"), table_name="snapshots")
    op.drop_table("snapshots")
    op.drop_table("networks")
    op.drop_index(op.f("ix_auth_sessions_expires_at"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("audit_events")
    op.drop_table("users")
