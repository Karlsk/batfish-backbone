from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.modules.leader.checks_models import CheckRunRecord
from app.modules.leader.checks_schemas import CheckRunStored


def _dto(row: CheckRunRecord | None) -> CheckRunStored | None:
    if row is None:
        return None
    return CheckRunStored.model_validate(
        {name: getattr(row, name) for name in CheckRunStored.model_fields}
    )


class CheckRunsRepository:
    def __init__(self, transaction):
        self._transaction = transaction

    def reserve(self, **values) -> tuple[CheckRunStored, bool]:
        statement = (
            insert(CheckRunRecord)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_check_runs_actor_key")
        )
        created = self._transaction.execute(statement).rowcount == 1
        row = self._transaction.scalar(
            select(CheckRunRecord).where(
                CheckRunRecord.created_by == values["created_by"],
                CheckRunRecord.idempotency_key == values["idempotency_key"],
            )
        )
        return _dto(row), created

    def by_key(self, actor_id: UUID, key: str) -> CheckRunStored | None:
        row = self._transaction.scalar(
            select(CheckRunRecord).where(
                CheckRunRecord.created_by == actor_id, CheckRunRecord.idempotency_key == key
            )
        )
        return _dto(row)

    def get(self, identifier: UUID) -> CheckRunStored | None:
        return _dto(self._transaction.get(CheckRunRecord, identifier))

    def lock(self, identifier: UUID) -> CheckRunStored:
        row = self._transaction.scalar(
            select(CheckRunRecord).where(CheckRunRecord.id == identifier).with_for_update()
        )
        return _dto(row)

    def list(self, *, network_id: UUID | None, offset: int, limit: int):
        where = [] if network_id is None else [CheckRunRecord.network_id == network_id]
        rows = self._transaction.scalars(
            select(CheckRunRecord)
            .where(*where)
            .order_by(CheckRunRecord.created_at.desc(), CheckRunRecord.id.desc())
            .offset(offset)
            .limit(limit)
        )
        total = self._transaction.scalar(
            select(func.count()).select_from(CheckRunRecord).where(*where)
        )
        return tuple(_dto(row) for row in rows), total

    def dispatched(self, identifier: UUID, *, job_ids: tuple[UUID, ...], derived_snapshot_id=None):
        row = self._transaction.get(CheckRunRecord, identifier, with_for_update=True)
        if row.submission_state == "submitting":
            row.job_ids = [str(item) for item in job_ids]
            row.derived_snapshot_id = derived_snapshot_id
            row.submission_state = "dispatched"
            row.updated_at = datetime.now(UTC)
            self._transaction.flush()
        return _dto(row)

    def succeeded(self, identifier: UUID):
        row = self._transaction.get(CheckRunRecord, identifier, with_for_update=True)
        if row.submission_state == "submitting":
            row.submission_state = "succeeded"
            row.updated_at = datetime.now(UTC)
            self._transaction.flush()
        return _dto(row)

    def failed(self, identifier: UUID, error_code: str):
        row = self._transaction.get(CheckRunRecord, identifier, with_for_update=True)
        if row.submission_state == "submitting":
            row.submission_state = "failed"
            row.error_code = error_code
            row.updated_at = datetime.now(UTC)
            self._transaction.flush()
        return _dto(row)
