from datetime import UTC, datetime

from sqlalchemy import func, or_, select

from app.modules.changes.models import Comparison
from app.modules.changes.schemas import ComparisonDTO


class ChangesRepository:
    def __init__(self, transaction):
        self.tx = transaction

    @staticmethod
    def dto(row):
        return (
            ComparisonDTO(**{field: getattr(row, field) for field in ComparisonDTO.model_fields})
            if row is not None
            else None
        )

    def get(self, identifier, *, lock=False):
        query = select(Comparison).where(
            Comparison.id == identifier, Comparison.deleted_at.is_(None)
        )
        if lock:
            query = query.with_for_update()
        return self.dto(self.tx.scalar(query))

    def list(self, network_id, offset, limit):
        query = select(Comparison).where(
            Comparison.network_id == network_id, Comparison.deleted_at.is_(None)
        )
        total = self.tx.scalar(select(func.count()).select_from(query.subquery()))
        rows = self.tx.scalars(
            query.order_by(Comparison.created_at.desc(), Comparison.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return tuple(self.dto(row) for row in rows), total

    def add(self, *, identifier, actor, network_id, baseline, candidate, name, coverage, notes):
        row = Comparison(
            id=identifier,
            network_id=network_id,
            baseline_snapshot_id=baseline.id,
            candidate_snapshot_id=candidate.id,
            display_name=name,
            baseline_content_hash=baseline.content_hash,
            candidate_content_hash=candidate.content_hash,
            baseline_engine_version=baseline.engine_version,
            candidate_engine_version=candidate.engine_version,
            baseline_sdk_version=baseline.sdk_version,
            candidate_sdk_version=candidate.sdk_version,
            engine_version=candidate.engine_version,
            sdk_version=candidate.sdk_version,
            coverage=coverage,
            coverage_notes=list(notes),
            created_by=actor.user_id,
        )
        self.tx.add(row)
        self.tx.flush()
        return self.dto(row)

    def has_active_reference(self, snapshot_id):
        return (
            self.tx.scalar(
                select(Comparison.id)
                .where(
                    Comparison.deleted_at.is_(None),
                    or_(
                        Comparison.baseline_snapshot_id == snapshot_id,
                        Comparison.candidate_snapshot_id == snapshot_id,
                    ),
                )
                .limit(1)
            )
            is not None
        )

    def soft_delete(self, identifier):
        row = self.tx.scalar(
            select(Comparison).where(Comparison.id == identifier).with_for_update()
        )
        if row is None or row.deleted_at is not None:
            return False
        row.deleted_at = datetime.now(UTC)
        self.tx.flush()
        return True
