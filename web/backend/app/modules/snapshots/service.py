import hashlib
from uuid import UUID, uuid4

from app.contracts.dto import Actor, AnalysisContext, ExecutionContext
from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.engine import EngineGate
from app.modules.auth.service import AuthService
from app.modules.jobs.service import JobsService
from app.modules.networks.service import NetworksService
from app.modules.snapshots.controller import SnapshotController
from app.modules.snapshots.repository import SnapshotsRepository
from app.modules.snapshots.schemas import (
    CreateSnapshotRequest,
    SnapshotCreated,
    SnapshotDTO,
    SnapshotPage,
)
from app.modules.uploads.service import UploadsService


class SnapshotsService:
    def __init__(
        self,
        database,
        auth: AuthService,
        networks: NetworksService,
        uploads: UploadsService,
        jobs: JobsService,
        controller: SnapshotController,
    ):
        self._database, self._auth, self._networks = database, auth, networks
        self._uploads, self._jobs, self._controller = uploads, jobs, controller

    def _stored(self, actor, network_id, snapshot_id):
        self._auth.revalidate_actor(actor)
        self._networks.get(actor, network_id)
        with self._database.transaction() as tx:
            row = SnapshotsRepository(tx).get(snapshot_id)
        if row is None or row.network_id != network_id:
            raise ServiceError(ErrorCode.NOT_FOUND)
        return row

    def _present(self, actor, row):
        status = row.status
        if status not in {"deleted", "deleting"} and row.initialization_job_id:
            job = self._jobs.get(actor, row.initialization_job_id)
            if job.status in {"failed", "cancelled", "interrupted"}:
                status = "failed"
            elif job.status == "queued":
                status = "queued"
            elif job.status == "running":
                status = "initializing"
            elif status not in {"ready", "ready_with_warnings"}:
                status = "failed"
        return SnapshotDTO(
            **(row.model_dump(include=set(SnapshotDTO.model_fields)) | {"status": status})
        )

    def get(self, actor, network_id, snapshot_id):
        return self._present(actor, self._stored(actor, network_id, snapshot_id))

    def list(self, actor, network_id, *, offset=0, limit=50):
        self._auth.revalidate_actor(actor)
        self._networks.get(actor, network_id)
        if offset < 0 or not 1 <= limit <= 200:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as tx:
            rows, total = SnapshotsRepository(tx).list(network_id, offset, limit)
        return SnapshotPage(
            items=tuple(self._present(actor, row) for row in rows),
            total=total,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    def _context(network, snapshot):
        return ExecutionContext(
            network_id=network.id,
            snapshot_id=snapshot.id,
            engine_network=network.engine_name,
            engine_snapshot=snapshot.engine_name,
            engine_version=snapshot.engine_version or "pending",
            sdk_version=snapshot.sdk_version or "pending",
            schema_version="1",
        )

    def create(
        self,
        actor,
        network_id,
        request: CreateSnapshotRequest,
        *,
        idempotency_key=None,
        retry_of=None,
    ):
        actor = self._auth.revalidate_actor(actor)
        network = self._networks.require_ready(actor, network_id)
        original = None
        if retry_of is not None:
            if EngineGate(self._database).state() == "unknown":
                raise ServiceError(ErrorCode.ENGINE_STATE_UNKNOWN)
            parent = self._jobs.get(actor, retry_of)
            if parent.kind != "initialization" or parent.status not in {
                "failed",
                "cancelled",
                "interrupted",
            }:
                raise ServiceError(ErrorCode.CONFLICT)
            if parent.created_by != actor.user_id and actor.role != "admin":
                raise ServiceError(ErrorCode.FORBIDDEN)
            original = self._stored(actor, network_id, parent.resource_ids["snapshot_id"])
            if original.manifest is None:
                raise ServiceError(ErrorCode.CONFLICT)
        with self._database.transaction() as tx:
            reservation = self._jobs.reserve_resource(
                actor,
                route="/snapshots" if retry_of is None else "/snapshots/retry",
                resource_key=str(network_id) + (":" + str(retry_of) if retry_of else ""),
                key=idempotency_key or uuid4().hex,
                request_hash=hashlib.sha256(request.model_dump_json().encode()).hexdigest(),
                resource_id=uuid4(),
                transaction=tx,
            )
            repository = SnapshotsRepository(tx)
            if not reservation.created:
                row = repository.get(reservation.resource_id)
                if row is None or row.initialization_job_id is None:
                    raise ServiceError(ErrorCode.CONFLICT)
                return SnapshotCreated(snapshot_id=row.id, job_id=row.initialization_job_id)
            manifest = (
                original.manifest
                if original
                else self._uploads.consume(actor, network_id, request.upload_id, transaction=tx)
            )
            row = repository.add(reservation.resource_id, actor, network, request, manifest)
            job = self._jobs.submit(
                actor,
                "initialization",
                self._context(network, row),
                request.model_dump(mode="json"),
                effective_parameters={"options": request.options.model_dump(mode="json")},
                transaction=tx,
                retry_of=retry_of,
            )
            repository.attach_job(row.id, job.id)
            return SnapshotCreated(snapshot_id=row.id, job_id=job.id)

    def retry(self, actor, job, *, idempotency_key=None):
        original = self._stored(actor, job.context.network_id, job.context.snapshot_id)
        request = CreateSnapshotRequest(
            display_name=original.display_name,
            upload_id=original.manifest.upload_id,
            options=original.initialization_options,
        )
        created = self.create(
            actor, original.network_id, request, idempotency_key=idempotency_key, retry_of=job.id
        )
        return self._jobs.get(actor, created.job_id)

    @staticmethod
    def quality(answer):
        statuses = [str(item.get("Status", "UNKNOWN")) for item in answer.parse_status]
        nodes = {str(node) for item in answer.parse_status for node in (item.get("Nodes") or ())}
        fatal = not nodes or not statuses or any(status == "FAILED" for status in statuses)
        warnings = any(status != "PASSED" for status in statuses) or bool(answer.issues)
        status = "failed" if fatal else "ready_with_warnings" if warnings else "ready"
        return status, {
            "file_count": len(statuses),
            "node_count": len(nodes),
            "issue_count": len(answer.issues),
            "parse_statuses": sorted(set(statuses)),
            "coverage": "unknown" if fatal else "limited" if warnings else "complete",
        }

    def execute(self, job):
        actor = self._auth.revalidate_actor(
            Actor(user_id=job.created_by, role="member", enabled=True)
        )
        row = self._stored(actor, job.context.network_id, job.context.snapshot_id)
        if row.initialization_job_id != job.id or row.manifest is None:
            raise ServiceError(ErrorCode.CONFLICT)
        self._networks.require_ready(actor, row.network_id)
        with self._uploads.materialize(row.manifest) as materialized:
            answer = self._controller.initialize(
                job.context, materialized, row.initialization_options
            )
        status, quality = self.quality(answer)
        with self._database.transaction() as tx:
            SnapshotsRepository(tx).complete(row.id, answer, status, quality)
        if status == "failed":
            raise ServiceError(ErrorCode.NOT_READY)
        return None

    def require_analyzable(self, actor, network_id: UUID, snapshot_id: UUID) -> AnalysisContext:
        network = self._networks.require_ready(actor, network_id)
        snapshot = self.get(actor, network_id, snapshot_id)
        if snapshot.status not in {"ready", "ready_with_warnings"}:
            raise ServiceError(ErrorCode.NOT_READY)
        return AnalysisContext(**self._context(network, snapshot).model_dump())
