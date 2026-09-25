import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.jobs.models import IdempotencyRecord


class IdempotencyRepository:
    def __init__(self, transaction: Session):
        self._transaction = transaction

    def reserve(
        self,
        *,
        actor_id: UUID,
        route: str,
        resource_key: str,
        key: str,
        request_hash: str,
        resource_id: UUID,
    ) -> tuple[UUID, str, bool]:
        scope = "\0".join([str(actor_id), route, resource_key, key])
        lock = int.from_bytes(hashlib.sha256(scope.encode()).digest()[:8], "big", signed=True)
        self._transaction.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        record = self._transaction.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.actor_id == actor_id,
                IdempotencyRecord.route == route,
                IdempotencyRecord.resource_key == resource_key,
                IdempotencyRecord.key == key,
            )
        )
        if record is not None:
            return record.resource_id, record.request_hash, False
        record = IdempotencyRecord(
            actor_id=actor_id,
            route=route,
            resource_key=resource_key,
            key=key,
            request_hash=request_hash,
            resource_id=resource_id,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        self._transaction.add(record)
        self._transaction.flush()
        return resource_id, request_hash, True
