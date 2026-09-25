from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class WorkerStatus(Base):
    __tablename__ = "worker_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(128))
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available: Mapped[bool] = mapped_column(Boolean)
    engine_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    engine_available: Mapped[bool] = mapped_column(Boolean, server_default="false")


class EngineReconciliation(Base):
    __tablename__ = "engine_reconciliations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    resolution: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
