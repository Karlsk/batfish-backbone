from uuid import UUID

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.database import Database
from app.modules.audit.service import AuditService
from app.modules.auth.service import AuthService
from app.modules.business_concerns.repository import BusinessConcernsRepository
from app.modules.business_concerns.schemas import (
    ConcernDTO,
    ConcernPage,
    CreateConcernRequest,
    PatchConcernRequest,
)
from app.modules.networks.service import NetworksService


class BusinessConcernsService:
    def __init__(self, database: Database, auth: AuthService, networks: NetworksService):
        self._database, self._auth, self._networks = database, auth, networks

    def _actor(self, actor: Actor, *, write: bool = False) -> Actor:
        actor = self._auth.revalidate_actor(actor)
        if write and actor.role != "admin":
            raise ServiceError(ErrorCode.FORBIDDEN)
        return actor

    def active_counts(self, actor: Actor, network_ids: tuple[UUID, ...]) -> dict[UUID, int]:
        self._actor(actor)
        if len(network_ids) > 200:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as transaction:
            return BusinessConcernsRepository(transaction).active_counts(network_ids)

    def list(
        self,
        actor: Actor,
        *,
        network_id: UUID | None,
        include_archived: bool,
        offset: int,
        limit: int,
    ) -> ConcernPage:
        self._actor(actor)
        if network_id is not None:
            self._networks.get(actor, network_id)
        with self._database.transaction() as transaction:
            items, total = BusinessConcernsRepository(transaction).list(
                network_id=network_id, include_archived=include_archived, offset=offset, limit=limit
            )
            return ConcernPage(items=tuple(items), offset=offset, limit=limit, total=total)

    def get(self, actor: Actor, identifier: UUID, *, version: int | None = None) -> ConcernDTO:
        self._actor(actor)
        with self._database.transaction() as transaction:
            concern = BusinessConcernsRepository(transaction).get(identifier, version=version)
            if concern is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            return concern

    def create(
        self, actor: Actor, request: CreateConcernRequest, *, request_id: UUID
    ) -> ConcernDTO:
        actor = self._actor(actor, write=True)
        self._networks.get(actor, request.network_id)
        with self._database.transaction() as transaction:
            concern = BusinessConcernsRepository(transaction).create(
                network_id=request.network_id,
                actor_id=actor.user_id,
                name=request.name,
                description=request.description,
                priority=request.priority,
                flows=[flow.model_dump(mode="json") for flow in request.flows],
            )
            AuditService().record(
                transaction=transaction,
                actor_id=actor.user_id,
                action="business_concern.create",
                resource_id=concern.id,
                outcome="created",
                request_id=request_id,
            )
            return concern

    def update(
        self, actor: Actor, identifier: UUID, request: PatchConcernRequest, *, request_id: UUID
    ) -> ConcernDTO:
        actor = self._actor(actor, write=True)
        with self._database.transaction() as transaction:
            repository = BusinessConcernsRepository(transaction)
            current = repository.get(identifier, lock=True)
            if current is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            if current.version != request.expected_version:
                raise ServiceError(ErrorCode.CONFLICT)
            changed = request.model_fields_set
            concern = repository.update(
                identifier,
                actor_id=actor.user_id,
                name=request.name if "name" in changed else current.name,
                description=request.description
                if "description" in changed
                else current.description,
                priority=request.priority if "priority" in changed else current.priority,
                flows=(
                    [flow.model_dump(mode="json") for flow in request.flows]
                    if "flows" in changed
                    else [flow.model_dump(mode="json") for flow in current.flows]
                ),
                archived=request.archived if "archived" in changed else current.archived,
            )
            AuditService().record(
                transaction=transaction,
                actor_id=actor.user_id,
                action="business_concern.archive"
                if concern.archived and not current.archived
                else "business_concern.update",
                resource_id=identifier,
                outcome="archived" if concern.archived and not current.archived else "updated",
                request_id=request_id,
            )
            return concern
