from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class BusinessConcern(Base):
    __tablename__ = "business_concerns"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    network_id: Mapped[UUID] = mapped_column(ForeignKey("networks.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(8))
    flows: Mapped[list] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("priority IN ('high', 'medium', 'low')", name="priority"),
    )


class BusinessConcernVersion(Base):
    __tablename__ = "business_concern_versions"
    concern_id: Mapped[UUID] = mapped_column(ForeignKey("business_concerns.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    network_id: Mapped[UUID] = mapped_column(ForeignKey("networks.id"))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(8))
    flows: Mapped[list] = mapped_column(JSONB)
    archived: Mapped[bool] = mapped_column(Boolean)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("priority IN ('high', 'medium', 'low')", name="priority"),
    )
