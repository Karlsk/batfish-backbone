from uuid import uuid4

from app.contracts.dto import Actor, ExecutionContext
from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.engine import EngineBusy, EngineOutcomeUnknown
from app.modules.audit.service import AuditService
from app.modules.auth.service import AuthService
from app.modules.jobs.service import JobsService
from app.modules.lifecycle.schemas import DeletionOutcome
from app.modules.networks.service import NetworksService
from app.modules.snapshots.service import SnapshotsService


class ResourceLifecycleService:
    def __init__(
        self,
        auth: AuthService,
        jobs: JobsService,
        networks: NetworksService,
        snapshots: SnapshotsService,
    ):
        self._auth, self._jobs, self._networks, self._snapshots = auth, jobs, networks, snapshots

    def _admin(self, actor):
        actor = self._auth.revalidate_actor(actor)
        if actor.role != "admin":
            raise ServiceError(ErrorCode.FORBIDDEN)
        return actor

    def _domain(self, job):
        return self._snapshots if job.context.snapshot_id else self._networks

    def delete(self, actor, network_id, snapshot_id=None, *, request_id=None):
        actor = self._admin(actor)
        with self._jobs.resource_boundary() as tx:
            network = self._networks.require_ready(actor, network_id)
            self._jobs.require_no_active(network_id, snapshot_id, transaction=tx)
            if snapshot_id:
                resource = self._snapshots.get(actor, network_id, snapshot_id)
                previous = resource.status
                if previous in {"deleting", "deleted"}:
                    raise ServiceError(ErrorCode.CONFLICT)
            else:
                self._snapshots.require_empty_network(network_id, transaction=tx)
                resource, previous = network, network.sync_state
            context = ExecutionContext(
                network_id=network.id,
                snapshot_id=snapshot_id,
                engine_network=network.engine_name,
                engine_snapshot=resource.engine_name if snapshot_id else None,
                engine_version=getattr(resource, "engine_version", None) or "pending",
                sdk_version=getattr(resource, "sdk_version", None) or "pending",
                schema_version="1",
            )
            job = self._jobs.submit(
                actor, "deletion", context, {"previous_state": previous}, transaction=tx
            )
            if snapshot_id:
                self._snapshots.mark_deleting(
                    actor, network_id, snapshot_id, job.id, transaction=tx
                )
            else:
                self._networks.mark_deleting(actor, network_id, job.id, transaction=tx)
            AuditService().record(
                transaction=tx,
                actor_id=actor.user_id,
                action="resource.delete",
                resource_id=resource.id,
                outcome="queued",
                request_id=request_id or uuid4(),
            )
            return job

    def execute(self, job):
        self._admin(Actor(user_id=job.created_by, role="admin", enabled=True))
        domain = self._domain(job)
        domain.deletion_presence(job, remove=True)
        with self._jobs.resource_boundary() as tx:
            domain.finish_deletion(job, state="deleted", transaction=tx)
            AuditService().record(
                transaction=tx,
                actor_id=job.created_by,
                action="resource.delete.complete",
                resource_id=job.context.snapshot_id or job.context.network_id,
                outcome="deleted",
                request_id=job.id,
            )
        if job.context.snapshot_id:
            self._snapshots.cleanup_deleted(job)

    def reconcile(self, actor, job_id, *, note, request_id=None):
        actor = self._admin(actor)
        if not 10 <= len(note.strip()) <= 1000:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._jobs.resource_boundary() as tx:
            job = self._jobs.get(actor, job_id)
            if job.kind != "deletion" or job.status not in {"failed", "interrupted"}:
                raise ServiceError(ErrorCode.CONFLICT)
            self._jobs.require_no_active(
                job.context.network_id, job.context.snapshot_id, transaction=tx
            )
            domain = self._domain(job)
            row = domain.deletion_resource(job)
            if getattr(row, "status", getattr(row, "sync_state", None)) == "deleted":
                state = "deleted"
            else:
                try:
                    exists = domain.deletion_presence(job)
                except EngineBusy as error:
                    raise ServiceError(
                        ErrorCode.ENGINE_STATE_UNKNOWN if error.unknown else ErrorCode.NOT_READY
                    ) from None
                except EngineOutcomeUnknown:
                    raise ServiceError(ErrorCode.ENGINE_STATE_UNKNOWN) from None
                state = job.requested_parameters["previous_state"] if exists else "deleted"
                domain.finish_deletion(job, state=state, transaction=tx)
            AuditService().record(
                transaction=tx,
                actor_id=actor.user_id,
                action="resource.delete.reconcile",
                note=note.strip(),
                resource_id=row.id,
                outcome=state,
                request_id=request_id or uuid4(),
            )
        if state == "deleted" and job.context.snapshot_id:
            self._snapshots.cleanup_deleted(job)
        return DeletionOutcome(resource_id=row.id, state=state)
