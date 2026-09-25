from uuid import UUID

from sqlalchemy.orm import Session

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.contracts.idempotency import ResourceReservation
from app.modules.jobs.repository import IdempotencyRepository


class JobsService:
    """MVP-06 resource idempotency; job lifecycle is added in MVP-08."""

    def reserve_resource(
        self,
        actor: Actor,
        *,
        route: str,
        resource_key: str,
        key: str,
        request_hash: str,
        resource_id: UUID,
        transaction: Session,
    ) -> ResourceReservation:
        if not 1 <= len(key) <= 128:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        stored_id, stored_hash, created = IdempotencyRepository(transaction).reserve(
            actor_id=actor.user_id,
            route=route,
            resource_key=resource_key,
            key=key,
            request_hash=request_hash,
            resource_id=resource_id,
        )
        if stored_hash != request_hash or stored_id is None:
            raise ServiceError(ErrorCode.CONFLICT)
        return ResourceReservation(stored_id, created)
