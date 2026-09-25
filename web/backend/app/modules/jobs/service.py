import hashlib
import json
import re
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.contracts.dto import Actor, AnalysisContext, JobDTO
from app.contracts.errors import ErrorCode, ErrorDetail, ServiceError
from app.contracts.idempotency import ResourceReservation
from app.infrastructure.engine import EngineGate
from app.infrastructure.settings import Settings
from app.modules.auth.service import AuthService
from app.modules.jobs.repository import IdempotencyRepository, JobsRepository
from app.modules.jobs.schemas import TRANSITIONS, JobInput, JobPage


class JobsService:
    """Durable metadata operations; SDK work belongs to the independent worker."""

    def __init__(
        self, database=None, auth: AuthService | None = None, settings: Settings | None = None
    ):
        self._database, self._auth = database, auth
        self._settings = settings or Settings()

    @staticmethod
    def _present(job: JobDTO) -> JobDTO:
        return job.model_copy(
            update={"cancel_allowed": job.status == "queued" and job.kind != "deletion"}
        )

    def _actor(self, actor):
        if self._database is None or self._auth is None:
            raise ServiceError(ErrorCode.NOT_READY)
        return self._auth.revalidate_actor(actor)

    def submit(
        self,
        actor: Actor,
        kind: str,
        context: AnalysisContext,
        parameters,
        idempotency_key: str | None = None,
        *,
        effective_parameters=None,
        retry_of: UUID | None = None,
        transaction: Session | None = None,
    ) -> JobDTO:
        actor = self._actor(actor)
        try:
            request = JobInput(
                kind=kind,
                context=context,
                requested_parameters=parameters,
                effective_parameters=parameters
                if effective_parameters is None
                else effective_parameters,
            )
        except ValidationError:
            raise ServiceError(ErrorCode.VALIDATION_ERROR) from None
        if request.kind == "deletion" and actor.role != "admin":
            raise ServiceError(ErrorCode.FORBIDDEN)
        key = idempotency_key if idempotency_key is not None else uuid4().hex
        if not re.fullmatch(r"[!-~]{1,128}", key):
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        context = request.context
        scope = ":".join(
            str(value or "")
            for value in (context.network_id, context.snapshot_id, context.reference_snapshot_id)
        )
        digest = hashlib.sha256(
            json.dumps(
                {
                    **request.model_dump(mode="json"),
                    **({"retry_of": str(retry_of)} if retry_of else {}),
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        with (
            nullcontext(transaction) if transaction is not None else self._database.transaction()
        ) as session:
            repository = JobsRepository(session)
            repository.lock_queue()
            if retry_of is not None:
                parent = repository.get(retry_of)
                if (
                    parent is None
                    or parent.kind != request.kind
                    or parent.status not in {"failed", "interrupted", "cancelled"}
                    or parent.kind == "deletion"
                ):
                    raise ServiceError(ErrorCode.CONFLICT)
                if parent.created_by != actor.user_id and actor.role != "admin":
                    raise ServiceError(ErrorCode.FORBIDDEN)
            reservation = self.reserve_resource(
                actor,
                route="/jobs/" + request.kind,
                resource_key=scope,
                key=key,
                request_hash=digest,
                resource_id=uuid4(),
                transaction=session,
            )
            if not reservation.created:
                job = repository.get(reservation.resource_id)
                if job is None:
                    raise ServiceError(ErrorCode.CONFLICT)
                return self._present(job)
            global_count, user_count = repository.queued_counts(actor.user_id)
            if (
                global_count >= self._settings.max_queued_jobs_global
                or user_count >= self._settings.max_queued_jobs_per_user
            ):
                raise ServiceError(ErrorCode.RATE_LIMITED, retryable=True)
            job = repository.add(
                identifier=reservation.resource_id,
                actor_id=actor.user_id,
                request=request,
                retry_of=retry_of,
            )
            repository.bind_idempotency(job.id)
            return self._present(job)

    def list(
        self, actor, *, status=None, network_id=None, created_by=None, offset=0, limit=50
    ) -> JobPage:
        self._actor(actor)
        if offset < 0 or not 1 <= limit <= 200 or status is not None and status not in TRANSITIONS:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as transaction:
            rows, total = JobsRepository(transaction).list(
                status=status,
                network_id=network_id,
                created_by=created_by,
                offset=offset,
                limit=limit,
            )
            return JobPage(
                items=tuple(self._present(job) for job in rows),
                total=total,
                offset=offset,
                limit=limit,
            )

    def get(self, actor, job_id: UUID) -> JobDTO:
        self._actor(actor)
        with self._database.transaction() as transaction:
            job = JobsRepository(transaction).get(job_id)
            if job is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            return self._present(job)

    def cancel(self, actor, job_id: UUID) -> JobDTO:
        actor = self._actor(actor)
        with self._database.transaction() as transaction:
            repository = JobsRepository(transaction)
            job = repository.get(job_id, lock=True)
            if job is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            if job.created_by != actor.user_id and actor.role != "admin":
                raise ServiceError(ErrorCode.FORBIDDEN)
            if job.kind == "deletion" or "cancelled" not in TRANSITIONS[job.status]:
                raise ServiceError(ErrorCode.CONFLICT)
            updated = repository.transition(
                job_id,
                expected="queued",
                status="cancelled",
                phase="cancelled",
                cancel_allowed=False,
                finished_at=datetime.now(UTC),
            )
            if updated is None:
                raise ServiceError(ErrorCode.CONFLICT)
            return self._present(updated)

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

    def claim(self, worker_id: str) -> JobDTO | None:
        if not worker_id or len(worker_id) > 128:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as transaction:
            repository = JobsRepository(transaction)
            repository.lock_queue()
            if EngineGate(self._database).state(transaction=transaction) != "idle":
                return None
            job = repository.claim_candidate()
            if job is None:
                return None
            now = datetime.now(UTC)
            return repository.transition(
                job.id,
                expected="queued",
                status="running",
                phase="starting",
                lease_owner=worker_id,
                heartbeat_at=now,
                started_at=now,
                attempt=job.attempt + 1,
                cancel_allowed=False,
            )

    def set_phase(self, job_id, worker_id, phase):
        if phase not in {"checking_cache", "querying", "dataplane_or_query"}:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as transaction:
            repository = JobsRepository(transaction)
            job = repository.get(job_id, lock=True)
            if job is None or job.status != "running" or job.lease_owner != worker_id:
                raise ServiceError(ErrorCode.CONFLICT)
            return repository.transition(job_id, expected="running", status="running", phase=phase)

    def heartbeat(self, job_id, worker_id):
        with self._database.transaction() as transaction:
            JobsRepository(transaction).heartbeat(job_id, worker_id)

    def finish(self, job_id, worker_id, *, status, result_id=None, error=None, transaction=None):
        if status not in TRANSITIONS["running"]:
            raise ServiceError(ErrorCode.CONFLICT)
        with (
            nullcontext(transaction) if transaction is not None else self._database.transaction()
        ) as transaction:
            repository = JobsRepository(transaction)
            job = repository.get(job_id, lock=True)
            if job is None or job.status != "running" or job.lease_owner != worker_id:
                return None
            return repository.transition(
                job_id,
                expected="running",
                status=status,
                phase=status,
                finished_at=datetime.now(UTC),
                lease_owner=None,
                result_id=result_id,
                error=error.model_dump(mode="json") if error else None,
                engine_state="unknown" if status == "interrupted" else "idle",
                cancel_allowed=False,
            )

    def interrupt(self, job_id, worker_id):
        with self._database.transaction() as transaction:
            repository = JobsRepository(transaction)
            job = repository.get(job_id, lock=True)
            if job is None or job.status != "running" or job.lease_owner != worker_id:
                return None
            EngineGate(self._database).mark_unknown(transaction=transaction)
            return repository.transition(
                job_id,
                expected="running",
                status="interrupted",
                phase="interrupted",
                finished_at=datetime.now(UTC),
                lease_owner=None,
                engine_state="unknown",
                cancel_allowed=False,
                error=ErrorDetail(
                    code=ErrorCode.ENGINE_STATE_UNKNOWN,
                    message="Engine state unknown; administrator reconciliation required",
                    request_id=str(uuid4()),
                ).model_dump(mode="json"),
            )

    def recover_stale(self):
        with self._database.transaction() as transaction:
            repository = JobsRepository(transaction)
            repository.lock_queue()
            stale = repository.stale(
                datetime.now(UTC) - timedelta(seconds=self._settings.worker_stale_seconds)
            )
            for job in stale:
                EngineGate(self._database).mark_unknown(transaction=transaction)
                repository.transition(
                    job.id,
                    expected="running",
                    status="interrupted",
                    phase="interrupted",
                    finished_at=datetime.now(UTC),
                    lease_owner=None,
                    engine_state="unknown",
                    cancel_allowed=False,
                    error=ErrorDetail(
                        code=ErrorCode.ENGINE_STATE_UNKNOWN,
                        message="Worker lost; engine outcome requires reconciliation",
                        request_id=str(uuid4()),
                    ).model_dump(mode="json"),
                )
            return len(stale)

    def interrupted_ids(self):
        with self._database.transaction() as transaction:
            return JobsRepository(transaction).interrupted_ids()
