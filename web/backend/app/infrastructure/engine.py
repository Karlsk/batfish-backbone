"""Single-engine exclusion across processes, with conservative crash fencing."""

import sys
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base, Database

ENGINE_LOCK_ID = 4281062026


class EngineSlot(Base):
    __tablename__ = "engine_slot"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(16))
    owner: Mapped[str | None] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("state IN ('idle', 'busy', 'unknown')", name="state"),
    )


class EngineBusy(RuntimeError):
    def __init__(self, *, unknown: bool = False):
        super().__init__("ENGINE_UNKNOWN" if unknown else "ENGINE_BUSY")
        self.unknown = unknown


class EngineOutcomeUnknown(RuntimeError):
    pass


class EngineGate:
    def __init__(self, database: Database):
        self._database = database

    def state(self, *, transaction=None):
        if transaction is not None:
            return transaction.scalar(select(EngineSlot.state).where(EngineSlot.id == 1)) or "idle"
        with self._database.transaction() as session:
            return self.state(transaction=session)

    def view(self):
        with self._database.transaction() as session:
            row = session.get(EngineSlot, 1)
            return {
                "state": row.state if row else "idle",
                "owner": row.owner if row else None,
                "updated_at": row.updated_at if row else None,
            }

    def mark_unknown(self, *, transaction):
        transaction.execute(
            insert(EngineSlot)
            .values(id=1, state="unknown")
            .on_conflict_do_update(
                index_elements=[EngineSlot.id], set_={"state": "unknown", "updated_at": func.now()}
            )
        )

    def detect_abandoned(self):
        with self._database.transaction() as transaction:
            if transaction.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": ENGINE_LOCK_ID}
            ):
                if self.state(transaction=transaction) == "busy":
                    self.mark_unknown(transaction=transaction)

    def reconcile(self, *, transaction):
        acquired = transaction.scalar(
            text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": ENGINE_LOCK_ID}
        )
        if not acquired or self.state(transaction=transaction) != "unknown":
            raise EngineBusy()
        transaction.execute(
            update(EngineSlot)
            .where(EngineSlot.id == 1)
            .values(state="idle", owner=None, updated_at=func.now())
        )

    @contextmanager
    def exclusive(self, *, owner: str):
        with self._database.engine.connect() as connection:
            try:
                acquired = connection.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": ENGINE_LOCK_ID}
                )
            except BaseException:
                # If the reply was lost, acquisition itself may have succeeded remotely.
                connection.invalidate()
                raise
            if not acquired:
                raise EngineBusy()
            try:
                connection.commit()
                connection.execute(
                    insert(EngineSlot).values(id=1, state="idle").on_conflict_do_nothing()
                )
                state = connection.scalar(select(EngineSlot.state).where(EngineSlot.id == 1))
                if state != "idle":
                    connection.execute(
                        update(EngineSlot)
                        .where(EngineSlot.id == 1)
                        .values(state="unknown", updated_at=func.now())
                    )
                    connection.commit()
                    raise EngineBusy(unknown=True)
                admission = connection.execute(
                    update(EngineSlot)
                    .where(EngineSlot.id == 1, EngineSlot.state == "idle")
                    .values(state="busy", owner=owner, updated_at=func.now())
                )
                connection.commit()
                if admission.rowcount != 1:
                    raise EngineBusy(unknown=True)
                try:
                    yield
                except BaseException as failure:
                    try:
                        connection.execute(
                            update(EngineSlot)
                            .where(EngineSlot.id == 1)
                            .values(state="unknown", updated_at=func.now())
                        )
                        connection.commit()
                    finally:
                        if isinstance(failure, Exception):
                            raise EngineOutcomeUnknown(
                                "Engine outcome requires reconciliation"
                            ) from None
                    raise
                else:
                    try:
                        completed = connection.execute(
                            update(EngineSlot)
                            .where(
                                EngineSlot.id == 1,
                                EngineSlot.state == "busy",
                                EngineSlot.owner == owner,
                            )
                            .values(state="idle", owner=None, updated_at=func.now())
                        )
                        connection.commit()
                        if completed.rowcount != 1:
                            raise EngineOutcomeUnknown("Engine was fenced while work was running")
                    except Exception:
                        raise EngineOutcomeUnknown(
                            "Engine slot completion requires reconciliation"
                        ) from None
            finally:
                pending_error = sys.exc_info()[0] is not None
                try:
                    connection.rollback()
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": ENGINE_LOCK_ID}
                    )
                    connection.commit()
                except BaseException:
                    # A session lock must never return to the connection pool still held.
                    connection.invalidate()
                    if not pending_error:
                        raise
