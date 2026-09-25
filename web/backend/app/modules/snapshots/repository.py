from sqlalchemy import func, select

from app.modules.snapshots.models import Snapshot
from app.modules.snapshots.schemas import StoredSnapshot


class SnapshotsRepository:
    def __init__(self, transaction):
        self.tx = transaction

    @staticmethod
    def dto(row):
        return (
            StoredSnapshot(**{field: getattr(row, field) for field in StoredSnapshot.model_fields})
            if row
            else None
        )

    def get(self, identifier):
        return self.dto(self.tx.get(Snapshot, identifier))

    def add(self, identifier, actor, network, request, manifest):
        row = Snapshot(
            id=identifier,
            network_id=network.id,
            engine_name="bfw-snapshot-" + identifier.hex,
            display_name=request.display_name,
            content_hash=manifest.content_hash,
            manifest=manifest.model_dump(mode="json"),
            initialization_options=request.options.model_dump(mode="json"),
            created_by=actor.user_id,
        )
        self.tx.add(row)
        self.tx.flush()
        return self.dto(row)

    def attach_job(self, identifier, job_id):
        self.tx.get(Snapshot, identifier).initialization_job_id = job_id
        self.tx.flush()

    def complete(self, identifier, answer, status, quality):
        row = self.tx.get(Snapshot, identifier)
        row.status, row.quality_summary = status, quality
        row.engine_version, row.sdk_version = answer.engine_version, answer.sdk_version
        row.diagnostics = answer.model_dump(mode="json")

    def list(self, network_id, offset, limit):
        query = select(Snapshot).where(
            Snapshot.network_id == network_id, Snapshot.deleted_at.is_(None)
        )
        total = self.tx.scalar(select(func.count()).select_from(query.subquery()))
        rows = self.tx.scalars(
            query.order_by(Snapshot.created_at.desc(), Snapshot.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return tuple(self.dto(row) for row in rows), total
