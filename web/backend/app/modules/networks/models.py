from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Network(Base):
    __tablename__ = "networks"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    display_name: Mapped[str] = mapped_column(String(255))
    engine_name: Mapped[str] = mapped_column(String(128), unique=True)
    sync_state: Mapped[str] = mapped_column(String(16), server_default="pending")
    sync_error: Mapped[str | None] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint(
            "sync_state IN ('pending', 'ready', 'failed', 'deleting', 'deleted')", name="sync_state"
        ),
    )
