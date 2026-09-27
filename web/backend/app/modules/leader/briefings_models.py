from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class BriefingRecord(Base):
    __tablename__ = "briefings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    network_id: Mapped[UUID] = mapped_column(index=True)
    latest_version: Mapped[int] = mapped_column(Integer)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("latest_version >= 1", name="latest_version"),)


class BriefingRevision(Base):
    __tablename__ = "briefing_revisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("briefings.id"))
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(String(4000))
    frozen: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("report_id", "version", name="uq_briefing_report_version"),
        UniqueConstraint("created_by", "idempotency_key", name="uq_briefing_actor_key"),
        CheckConstraint("version >= 1", name="version"),
        Index("ix_briefing_revisions_report", "report_id", "version"),
    )
