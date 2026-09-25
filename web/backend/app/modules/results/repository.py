from uuid import UUID

from sqlalchemy.orm import Session

from app.contracts.dto import ResultEnvelope
from app.infrastructure.storage import validate_key
from app.modules.results.models import Result


class ResultsRepository:
    """Metadata only. The service must publish the file before committing this transaction."""

    def __init__(self, transaction: Session):
        self._transaction = transaction

    def add(self, envelope: ResultEnvelope, *, storage_key: str) -> None:
        data = envelope.model_dump(mode="json")
        self._transaction.add(
            Result(
                **{**data, "id": envelope.id, "created_at": envelope.created_at},
                network_id=envelope.context.network_id,
                snapshot_id=envelope.context.snapshot_id,
                reference_snapshot_id=envelope.context.reference_snapshot_id,
                storage_key=validate_key(storage_key),
            )
        )
        self._transaction.flush()

    def get(self, result_id: UUID) -> ResultEnvelope | None:
        result = self._transaction.get(Result, result_id)
        if result is None:
            return None
        return ResultEnvelope.model_validate(
            {name: getattr(result, name) for name in ResultEnvelope.model_fields}
        )

    def storage_key(self, result_id: UUID) -> str | None:
        result = self._transaction.get(Result, result_id)
        return result.storage_key if result else None
