from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audit.repository import record


class AuditService:
    def record(
        self,
        *,
        transaction: Session,
        actor_id: UUID,
        action: str,
        resource_id: UUID | None,
        outcome: str,
        request_id: UUID,
    ) -> None:
        record(
            transaction,
            actor_id=actor_id,
            action=action,
            resource_id=resource_id,
            outcome=outcome,
            request_id=request_id,
        )
