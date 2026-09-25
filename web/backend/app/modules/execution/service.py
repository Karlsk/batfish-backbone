import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ErrorDetail, ServiceError
from app.infrastructure.engine import EngineBusy, EngineGate
from app.infrastructure.settings import Settings
from app.infrastructure.worker import worker_is_stopped
from app.modules.audit.service import AuditService
from app.modules.auth.service import AuthService
from app.modules.execution.repository import ExecutionRepository
from app.modules.execution.schemas import EngineStatus, Handler, ReconcileRequest
from app.modules.jobs.service import JobsService


class ExecutionService:
    def __init__(
        self,
        database,
        auth: AuthService,
        jobs: JobsService,
        *,
        handlers: dict[str, Handler] | None = None,
        controller=None,
        settings=None,
        clock=time.monotonic,
    ):
        self._database, self._auth, self._jobs = database, auth, jobs
        self._handlers = dict(handlers or {})
        self._controller = controller
        self._settings = settings or Settings()
        self._clock = clock
        self._gate = EngineGate(database)
        self._current = None
        self._started = None
        self.stop_requested = False

    def heartbeat(self, worker_id, *, available=True):
        with self._database.transaction() as transaction:
            ExecutionRepository(transaction).heartbeat(worker_id, available=available)
        current = self._current
        if current is not None:
            if self._clock() - self._started >= self._settings.job_wait_budget_seconds:
                self._jobs.interrupt(current.id, worker_id)
                self.stop_requested = True
            else:
                self._jobs.heartbeat(current.id, worker_id)

    def recover_stale(self):
        count = self._jobs.recover_stale()
        self._gate.detect_abandoned()
        return count

    def probe(self):
        if self._controller is None or self._gate.state() != "idle":
            return
        available = self._controller.probe()
        if available is not None:
            with self._database.transaction() as transaction:
                ExecutionRepository(transaction).probe(available)

    def observations(self):
        with self._database.transaction() as transaction:
            observations = ExecutionRepository(transaction).status()
            observations["database"] = {"available": True, "checked_at": datetime.now(UTC)}
            if self._gate.state(transaction=transaction) == "unknown":
                observations["engine"] = {"available": False, "checked_at": datetime.now(UTC)}
            return observations

    def _interruption_required(self):
        if self._clock() - self._started >= self._settings.job_wait_budget_seconds:
            self.stop_requested = True
        return self.stop_requested or self._gate.state() == "unknown"

    def run_once(self, worker_id):
        self.recover_stale()
        if self.stop_requested:
            return False
        job = self._jobs.claim(worker_id)
        if job is None:
            return False
        self._started = self._clock()
        self._current = job
        try:
            self.heartbeat(worker_id)
            if self.stop_requested:
                return True
            self._auth.revalidate_actor(Actor(user_id=job.created_by, role="member", enabled=True))
            handler = self._handlers.get(job.kind)
            if handler is None:
                raise ServiceError(ErrorCode.CONFLICT)
            result_id = handler.execute(job)
            if result_id is not None and not isinstance(result_id, UUID):
                raise TypeError("Handler must return a result identifier or None")
            if self._interruption_required():
                self._jobs.interrupt(job.id, worker_id)
            else:
                self._jobs.finish(job.id, worker_id, status="succeeded", result_id=result_id)
        except Exception as error:
            if self._interruption_required():
                self._jobs.interrupt(job.id, worker_id)
            else:
                code = error.code if isinstance(error, ServiceError) else ErrorCode.INTERNAL_ERROR
                self._jobs.finish(
                    job.id,
                    worker_id,
                    status="failed",
                    error=ErrorDetail(
                        code=code,
                        message="Task failed; review the error code and retry when its cause is resolved",
                        request_id=str(uuid4()),
                        retryable=isinstance(error, ServiceError) and error.retryable,
                    ),
                )
        finally:
            self._current = None
        return True

    def retry(self, actor, job_id, *, idempotency_key=None):
        actor = self._auth.revalidate_actor(actor)
        job = self._jobs.get(actor, job_id)
        if job.created_by != actor.user_id and actor.role != "admin":
            raise ServiceError(ErrorCode.FORBIDDEN)
        if job.status not in {"failed", "interrupted", "cancelled"} or job.kind == "deletion":
            raise ServiceError(ErrorCode.CONFLICT)
        if self._gate.state() == "unknown":
            raise ServiceError(ErrorCode.ENGINE_STATE_UNKNOWN)
        handler = self._handlers.get(job.kind)
        if handler is None or handler.retry is None:
            raise ServiceError(ErrorCode.CONFLICT)
        return handler.retry(actor, job, idempotency_key=idempotency_key or uuid4().hex)

    def engine_status(self, actor):
        actor = self._auth.revalidate_actor(actor)
        if actor.role != "admin":
            raise ServiceError(ErrorCode.FORBIDDEN)
        self.recover_stale()
        return EngineStatus(**self._gate.view(), interrupted_jobs=self._jobs.interrupted_ids())

    def reconcile(self, actor, *, resolution, note, request_id):
        actor = self._auth.revalidate_actor(actor)
        if actor.role != "admin":
            raise ServiceError(ErrorCode.FORBIDDEN)
        # Also protect direct service calls; invalid prose never reaches audit/storage.
        from pydantic import ValidationError

        try:
            request = ReconcileRequest(resolution=resolution, note=note.strip())
        except ValidationError:
            raise ServiceError(ErrorCode.VALIDATION_ERROR) from None
        with self._database.transaction() as transaction:
            if not worker_is_stopped(transaction):
                raise ServiceError(ErrorCode.CONFLICT)
            try:
                self._gate.reconcile(transaction=transaction)
            except EngineBusy:
                raise ServiceError(ErrorCode.CONFLICT) from None
            identifier = ExecutionRepository(transaction).reconciliation(
                actor.user_id, request.resolution, request.note
            )
            AuditService().record(
                transaction=transaction,
                actor_id=actor.user_id,
                action="engine.reconcile",
                resource_id=identifier,
                outcome="succeeded",
                request_id=request_id,
            )
        return EngineStatus(**self._gate.view(), interrupted_jobs=self._jobs.interrupted_ids())
