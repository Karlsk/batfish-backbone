from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(32))
    network_id: Mapped[UUID | None] = mapped_column(ForeignKey("networks.id"), index=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("snapshots.id"))
    resource_ids: Mapped[dict] = mapped_column(JSONB)
    requested_parameters: Mapped[dict] = mapped_column(JSONB)
    effective_parameters: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), server_default="queued", index=True)
    phase: Mapped[str] = mapped_column(String(128), server_default="queued")
    attempt: Mapped[int] = mapped_column(Integer, server_default="0")
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    engine_state: Mapped[str] = mapped_column(String(16), server_default="idle")
    cancel_allowed: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    result_id: Mapped[UUID | None] = mapped_column(ForeignKey("results.id"))
    error: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    context: Mapped[dict | None] = mapped_column(JSONB)
    retry_of: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"))
    __table_args__ = (
        CheckConstraint(
            "kind IN ('upload', 'initialization', 'analysis', 'deletion', 'fault_scenario')",
            name="kind",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted')",
            name="status",
        ),
        CheckConstraint("engine_state IN ('idle', 'busy', 'unknown')", name="engine_state"),
        CheckConstraint("attempt >= 0", name="attempt"),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    route: Mapped[str] = mapped_column(String(255))
    resource_key: Mapped[str] = mapped_column(String(128))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[UUID | None]
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("actor_id", "route", "resource_key", "key", name="uq_idempotency_scope"),
    )
