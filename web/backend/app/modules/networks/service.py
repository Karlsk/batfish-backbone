import hashlib
from uuid import UUID, uuid4

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.database import Database
from app.modules.auth.service import AuthService
from app.modules.jobs.service import JobsService
from app.modules.networks.controller import NetworkController
from app.modules.networks.repository import NetworksRepository
from app.modules.networks.schemas import (
    CreateNetworkRequest,
    NetworkDTO,
    NetworkPage,
    NetworkUnavailable,
)


class NetworksService:
    def __init__(
        self,
        database: Database,
        auth: AuthService,
        jobs: JobsService,
        controller: NetworkController,
    ):
        self._database, self._auth, self._jobs, self._controller = database, auth, jobs, controller

    def list(self, actor: Actor, *, offset: int = 0, limit: int = 50) -> NetworkPage:
        self._auth.revalidate_actor(actor)
        if offset < 0 or not 1 <= limit <= 200:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as transaction:
            rows, total = NetworksRepository(transaction).list(offset=offset, limit=limit)
            return NetworkPage(items=tuple(rows), offset=offset, limit=limit, total=total)

    def state_counts(self, actor: Actor) -> dict[str, int]:
        self._auth.revalidate_actor(actor)
        with self._database.transaction() as transaction:
            return NetworksRepository(transaction).state_counts()

    def get(self, actor: Actor, network_id: UUID) -> NetworkDTO:
        self._auth.revalidate_actor(actor)
        with self._database.transaction() as transaction:
            network = NetworksRepository(transaction).get(network_id)
            if network is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            return network

    def require_ready(self, actor: Actor, network_id: UUID) -> NetworkDTO:
        network = self.get(actor, network_id)
        if network.sync_state != "ready":
            raise ServiceError(ErrorCode.CONFLICT)
        return network

    def _problem(self, network_id: UUID, reason: str, *, failed: bool = False):
        try:
            with self._database.transaction() as transaction:
                NetworksRepository(transaction).mark_problem(network_id, reason, failed=failed)
        except Exception:
            # The committed pending identity survives even if the DB is temporarily unavailable.
            pass

    def create(
        self, actor: Actor, request: CreateNetworkRequest, *, idempotency_key: str | None = None
    ) -> NetworkDTO:
        actor = self._auth.revalidate_actor(actor)
        with self._database.transaction() as transaction:
            reservation = self._jobs.reserve_resource(
                actor,
                route="/networks",
                resource_key="global",
                key=idempotency_key or uuid4().hex,
                request_hash=hashlib.sha256(request.model_dump_json().encode()).hexdigest(),
                resource_id=uuid4(),
                transaction=transaction,
            )
            repository = NetworksRepository(transaction)
            network = (
                repository.add(
                    network_id=reservation.resource_id,
                    display_name=request.display_name,
                    actor_id=actor.user_id,
                )
                if reservation.created
                else repository.get(reservation.resource_id)
            )
            if network is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
        with self._jobs.resource_boundary():
            network = self.get(actor, network.id)
            if network.sync_state == "ready":
                return network
            if network.sync_state not in {"pending", "failed"}:
                raise ServiceError(ErrorCode.CONFLICT)
            try:
                self._controller.create(network.engine_name)
            except NetworkUnavailable as error:
                self._problem(network.id, error.reason, failed=error.failed)
                unknown = error.reason == "ENGINE_UNKNOWN"
                raise ServiceError(
                    ErrorCode.ENGINE_STATE_UNKNOWN if unknown else ErrorCode.NOT_READY,
                    retryable=not unknown,
                ) from None
            try:
                with self._database.transaction() as transaction:
                    NetworksRepository(transaction).mark_ready(network.id)
            except Exception:
                self._problem(network.id, "WRITEBACK_FAILED")
                raise ServiceError(ErrorCode.NOT_READY, retryable=True) from None
            return self.get(actor, network.id)

    def mark_deleting(self, actor, identifier, job_id, *, transaction):
        network = self.require_ready(actor, identifier)
        NetworksRepository(transaction).begin_deletion(network.id, job_id)

    def deletion_resource(self, job):
        with self._database.transaction() as tx:
            row = NetworksRepository(tx).lifecycle_get(job.context.network_id)
        if (
            row is None
            or row.deletion_job_id != job.id
            or row.sync_state not in {"deleting", "deleted"}
        ):
            raise ServiceError(ErrorCode.CONFLICT)
        return row

    def deletion_presence(self, job, *, remove=False):
        row = self.deletion_resource(job)
        return self._controller.deletion_presence(row.engine_name, remove=remove)

    def finish_deletion(self, job, *, state, transaction):
        self.deletion_resource(job)
        NetworksRepository(transaction).finish_deletion(job.context.network_id, state=state)
