from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    network_id: Mapped[UUID] = mapped_column(ForeignKey("networks.id"), index=True)
    engine_name: Mapped[str] = mapped_column(String(128), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64))
    initialization_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jobs.id", use_alter=True)
    )
    status: Mapped[str] = mapped_column(String(32), server_default="queued")
    quality_summary: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    manifest: Mapped[dict | None] = mapped_column(JSONB)
    initialization_options: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    diagnostics: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    engine_version: Mapped[str | None] = mapped_column(String(128))
    sdk_version: Mapped[str | None] = mapped_column(String(128))
    base_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("snapshots.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'initializing', 'ready', 'ready_with_warnings', 'failed', 'deleting', 'deleted')",
            name="status",
        ),
    )
