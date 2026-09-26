from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    network_id: Mapped[UUID] = mapped_column(ForeignKey("networks.id"), index=True)
    baseline_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("snapshots.id"), index=True)
    candidate_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("snapshots.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    baseline_content_hash: Mapped[str] = mapped_column(String(64))
    candidate_content_hash: Mapped[str] = mapped_column(String(64))
    baseline_engine_version: Mapped[str] = mapped_column(String(128))
    candidate_engine_version: Mapped[str] = mapped_column(String(128))
    baseline_sdk_version: Mapped[str] = mapped_column(String(128))
    candidate_sdk_version: Mapped[str] = mapped_column(String(128))
    engine_version: Mapped[str] = mapped_column(String(128))
    sdk_version: Mapped[str] = mapped_column(String(128))
    coverage: Mapped[str] = mapped_column(String(16))
    coverage_notes: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "baseline_snapshot_id <> candidate_snapshot_id", name="different_snapshots"
        ),
        CheckConstraint("coverage IN ('complete', 'limited')", name="coverage"),
    )
