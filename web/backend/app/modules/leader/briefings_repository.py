from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.modules.leader.briefings_models import BriefingRecord, BriefingRevision


class BriefingsRepository:
    def __init__(self, transaction):
        self._transaction = transaction

    def by_key(self, actor_id: UUID, key: str):
        return self._transaction.scalar(
            select(BriefingRevision).where(
                BriefingRevision.created_by == actor_id,
                BriefingRevision.idempotency_key == key,
            )
        )

    def revision(self, identifier: UUID):
        return self._transaction.get(BriefingRevision, identifier)

    def report(self, identifier: UUID, *, lock: bool = False):
        query = select(BriefingRecord).where(BriefingRecord.id == identifier)
        if lock:
            query = query.with_for_update()
        return self._transaction.scalar(query)

    def create(self, *, actor_id, network_id, title, notes, frozen, key, request_hash):
        now = datetime.now(UTC)
        report = BriefingRecord(
            id=uuid4(),
            network_id=network_id,
            latest_version=1,
            archived=False,
            created_by=actor_id,
            created_at=now,
        )
        revision = BriefingRevision(
            id=uuid4(),
            report_id=report.id,
            version=1,
            title=title,
            notes=notes,
            frozen=frozen,
            created_by=actor_id,
            created_at=now,
            idempotency_key=key,
            request_hash=request_hash,
        )
        self._transaction.add_all((report, revision))
        self._transaction.flush()
        return revision

    def revise(self, *, report, actor_id, title, notes, frozen, key, request_hash):
        report.latest_version += 1
        revision = BriefingRevision(
            id=uuid4(),
            report_id=report.id,
            version=report.latest_version,
            title=title,
            notes=notes,
            frozen=frozen,
            created_by=actor_id,
            created_at=datetime.now(UTC),
            idempotency_key=key,
            request_hash=request_hash,
        )
        self._transaction.add(revision)
        self._transaction.flush()
        return revision

    def list(self, *, network_id: UUID | None, include_archived: bool, offset: int, limit: int):
        conditions = []
        if network_id is not None:
            conditions.append(BriefingRecord.network_id == network_id)
        if not include_archived:
            conditions.append(BriefingRecord.archived.is_(False))
        rows = self._transaction.scalars(
            select(BriefingRevision)
            .join(BriefingRecord, BriefingRecord.id == BriefingRevision.report_id)
            .where(*conditions, BriefingRevision.version == BriefingRecord.latest_version)
            .order_by(BriefingRevision.created_at.desc(), BriefingRevision.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        total = self._transaction.scalar(
            select(func.count()).select_from(BriefingRecord).where(*conditions)
        )
        return rows, total or 0
