from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class CheckRunRecord(Base):
    __tablename__ = "check_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    template_id: Mapped[str] = mapped_column(String(64))
    template_version: Mapped[str] = mapped_column(String(16))
    network_id: Mapped[UUID] = mapped_column(ForeignKey("networks.id"))
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("snapshots.id"))
    concern_id: Mapped[UUID | None] = mapped_column(ForeignKey("business_concerns.id"))
    concern_version: Mapped[int | None] = mapped_column(Integer)
    frozen_concern: Mapped[dict | None] = mapped_column(JSONB)
    snapshot_quality: Mapped[dict] = mapped_column(JSONB)
    engine_version: Mapped[str] = mapped_column(String(128))
    sdk_version: Mapped[str] = mapped_column(String(128))
    effective_parameters: Mapped[dict] = mapped_column(JSONB)
    job_ids: Mapped[list] = mapped_column(JSONB)
    derived_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("snapshots.id"))
    submission_state: Mapped[str] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("created_by", "idempotency_key", name="uq_check_runs_actor_key"),
        CheckConstraint(
            "submission_state IN ('submitting','dispatched','succeeded','failed')",
            name="submission_state",
        ),
        Index("ix_check_runs_network_created", "network_id", "created_at"),
    )
