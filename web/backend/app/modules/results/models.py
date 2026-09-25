from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Result(Base):
    __tablename__ = "results"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(16))
    schema_version: Mapped[str] = mapped_column(String(32))
    network_id: Mapped[UUID] = mapped_column(ForeignKey("networks.id"))
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("snapshots.id"))
    reference_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("snapshots.id"))
    context: Mapped[dict] = mapped_column(JSONB)
    effective_parameters: Mapped[dict] = mapped_column(JSONB)
    summary: Mapped[dict] = mapped_column(JSONB)
    warnings: Mapped[list] = mapped_column(JSONB)
    coverage: Mapped[str] = mapped_column(String(16))
    truncated: Mapped[bool] = mapped_column(Boolean)
    truncation_reason: Mapped[str | None] = mapped_column(String(512))
    storage_key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("kind IN ('table', 'traces', 'graph', 'diff')", name="kind"),
        CheckConstraint("coverage IN ('complete', 'limited', 'unknown')", name="coverage"),
        CheckConstraint(
            "NOT truncated OR length(truncation_reason) > 0 AND truncation_reason IS NOT NULL",
            name="truncation_reason",
        ),
    )
