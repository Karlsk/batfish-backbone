from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from app.modules.execution.models import EngineReconciliation, WorkerStatus


class ExecutionRepository:
    def __init__(self, transaction):
        self._transaction = transaction

    def heartbeat(self, worker_id, *, available=True):
        now = datetime.now(UTC)
        self._transaction.execute(
            insert(WorkerStatus)
            .values(id=1, worker_id=worker_id, heartbeat_at=now, available=available)
            .on_conflict_do_update(
                index_elements=[WorkerStatus.id],
                set_={"worker_id": worker_id, "heartbeat_at": now, "available": available},
            )
        )

    def probe(self, available):
        self._transaction.execute(
            update(WorkerStatus)
            .where(WorkerStatus.id == 1)
            .values(engine_checked_at=datetime.now(UTC), engine_available=available)
        )

    def status(self):
        row = self._transaction.get(WorkerStatus, 1)
        if row is None:
            return {}
        return {
            "worker": {"available": row.available, "checked_at": row.heartbeat_at},
            "engine": {"available": row.engine_available, "checked_at": row.engine_checked_at},
        }

    def reconciliation(self, actor_id, resolution, note):
        row = EngineReconciliation(actor_id=actor_id, resolution=resolution, note=note)
        self._transaction.add(row)
        self._transaction.flush()
        return row.id
