import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session

from app.contracts.dto import JobDTO
from app.modules.jobs.models import IdempotencyRecord, Job


class IdempotencyRepository:
    def __init__(self, transaction: Session):
        self._transaction = transaction

    def find(self, *, actor_id: UUID, route: str, resource_key: str, key: str):
        record = self._transaction.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.actor_id == actor_id,
                IdempotencyRecord.route == route,
                IdempotencyRecord.resource_key == resource_key,
                IdempotencyRecord.key == key,
            )
        )
        return (record.resource_id, record.request_hash) if record else None

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


class JobsRepository:
    def __init__(self, transaction: Session):
        self._transaction = transaction

    @staticmethod
    def dto(row):
        if row is None:
            return None

        return JobDTO(
            **{field: getattr(row, field) for field in JobDTO.model_fields},
        )

    def get(self, job_id, *, lock=False):

        query = select(Job).where(Job.id == job_id)
        if lock:
            query = query.with_for_update()
        return self.dto(self._transaction.scalar(query))

    def get_many(self, job_ids):
        if not job_ids:
            return {}
        rows = self._transaction.scalars(select(Job).where(Job.id.in_(job_ids)))
        return {row.id: self.dto(row) for row in rows}

    def latest_analysis_for_snapshots(self, snapshot_ids):
        if not snapshot_ids:
            return {}
        rows = self._transaction.scalars(
            select(Job)
            .where(Job.snapshot_id.in_(snapshot_ids), Job.kind == "analysis")
            .distinct(Job.snapshot_id)
            .order_by(Job.snapshot_id, Job.created_at.desc(), Job.id.desc())
        )
        return {row.snapshot_id: self.dto(row) for row in rows}

    def analysis_status_counts(self):
        rows = self._transaction.execute(
            select(Job.status, func.count()).where(Job.kind == "analysis").group_by(Job.status)
        )
        return {status: count for status, count in rows}

    def lock_queue(self):
        self._transaction.execute(text("SELECT pg_advisory_xact_lock(4281082026)"))

    def has_active(self, network_id, snapshot_id=None):
        query = select(Job.id).where(
            Job.network_id == network_id, Job.status.in_(("queued", "running"))
        )
        if snapshot_id is not None:
            query = query.where(
                or_(
                    Job.snapshot_id == snapshot_id,
                    Job.context["reference_snapshot_id"].astext == str(snapshot_id),
                )
            )
        return self._transaction.scalar(query.limit(1)) is not None

    def queued_counts(self, actor_id):

        return self._transaction.execute(
            select(func.count(), func.count().filter(Job.created_by == actor_id))
            .select_from(Job)
            .where(Job.status == "queued")
        ).one()

    def add(self, *, identifier, actor_id, request, retry_of=None):

        context = request.context
        resources = {"network_id": str(context.network_id)}
        for field in ["snapshot_id", "reference_snapshot_id"]:
            if getattr(context, field) is not None:
                resources[field] = str(getattr(context, field))
        row = Job(
            id=identifier,
            kind=request.kind,
            network_id=context.network_id,
            snapshot_id=context.snapshot_id,
            resource_ids=resources,
            requested_parameters=request.model_dump(mode="json")["requested_parameters"],
            effective_parameters=request.model_dump(mode="json")["effective_parameters"],
            context=context.model_dump(mode="json"),
            retry_of=retry_of,
            created_by=actor_id,
            cancel_allowed=request.kind != "deletion",
        )
        self._transaction.add(row)
        self._transaction.flush()
        return self.dto(row)

    def bind_idempotency(self, identifier):

        self._transaction.execute(
            update(IdempotencyRecord)
            .where(IdempotencyRecord.resource_id == identifier)
            .values(job_id=identifier)
        )

    def list(self, *, status=None, network_id=None, created_by=None, offset=0, limit=50):

        filters = []
        for column, value in [
            (Job.status, status),
            (Job.network_id, network_id),
            (Job.created_by, created_by),
        ]:
            if value is not None:
                filters.append(column == value)
        total = self._transaction.scalar(select(func.count()).select_from(Job).where(*filters))
        rows = self._transaction.scalars(
            select(Job)
            .where(*filters)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return tuple(self.dto(row) for row in rows), total

    def transition(self, job_id, *, expected, status, **values):

        row = self._transaction.scalar(
            update(Job)
            .where(Job.id == job_id, Job.status == expected)
            .values(status=status, **values)
            .returning(Job)
        )
        return self.dto(row)

    def claim_candidate(self):
        if self._transaction.scalar(
            select(func.count()).select_from(Job).where(Job.status == "running")
        ):
            return None
        return self.dto(
            self._transaction.scalar(
                select(Job)
                .where(Job.status == "queued")
                .order_by(Job.created_at, Job.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
        )

    def heartbeat(self, job_id, worker_id):
        self._transaction.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == "running", Job.lease_owner == worker_id)
            .values(heartbeat_at=datetime.now(UTC))
        )

    def stale(self, cutoff):
        return tuple(
            self.dto(row)
            for row in self._transaction.scalars(
                select(Job)
                .where(
                    Job.status == "running",
                    (Job.heartbeat_at.is_(None) | (Job.heartbeat_at < cutoff)),
                )
                .with_for_update()
            )
        )

    def interrupted_ids(self):
        return tuple(
            self._transaction.scalars(
                select(Job.id)
                .where(Job.status == "interrupted", Job.engine_state == "unknown")
                .order_by(Job.created_at.desc())
                .limit(200)
            )
        )
