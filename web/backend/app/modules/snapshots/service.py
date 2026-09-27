import hashlib
from uuid import UUID, uuid4

from app.contracts.base import thaw
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
    Diagnostic,
    DiagnosticPage,
    InitializationAnswer,
    SnapshotCreated,
    SnapshotDTO,
    SnapshotFiles,
    SnapshotPage,
    SourceLocation,
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

    def _present(self, actor, row, jobs_by_id=None):
        status = row.status
        quality = thaw(row.quality_summary)
        if row.diagnostics:
            quality_status, quality = self.quality(
                InitializationAnswer.model_validate(thaw(row.diagnostics))
            )
            if status in {"ready", "ready_with_warnings"}:
                status = quality_status
        if status not in {"deleted", "deleting"} and row.initialization_job_id:
            job = (
                jobs_by_id.get(row.initialization_job_id)
                if jobs_by_id is not None
                else self._jobs.get(actor, row.initialization_job_id)
            )
            if job is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            if job.status in {"failed", "cancelled", "interrupted"}:
                status = "failed"
            elif job.status == "queued":
                status = "queued"
            elif job.status == "running":
                status = "initializing"
            elif job.status == "succeeded" and status in {"queued", "initializing"}:
                # Snapshot and job are read in separate transactions. A worker
                # can commit between those reads; let clients poll rather than
                # presenting a completed snapshot as a permanent failure.
                status = "initializing"
            elif status not in {"ready", "ready_with_warnings"}:
                status = "failed"
        return SnapshotDTO(
            **(
                row.model_dump(include=set(SnapshotDTO.model_fields))
                | {"status": status, "quality_summary": quality}
            )
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

    def latest_for_networks(self, actor: Actor, network_ids: tuple[UUID, ...]):
        self._auth.revalidate_actor(actor)
        if len(network_ids) > 200:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as tx:
            latest, ready = SnapshotsRepository(tx).latest_for_networks(network_ids)
        selected = (*latest.values(), *ready.values())
        job_ids = tuple(
            {row.initialization_job_id for row in selected if row.initialization_job_id is not None}
        )
        jobs = self._jobs.get_many(actor, job_ids)
        return (
            {identifier: self._present(actor, row, jobs) for identifier, row in latest.items()},
            {identifier: self._present(actor, row, jobs) for identifier, row in ready.items()},
        )

    def status_counts(self, actor: Actor) -> dict[str, int]:
        self._auth.revalidate_actor(actor)
        with self._database.transaction() as tx:
            return SnapshotsRepository(tx).status_counts()

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
        with self._jobs.resource_boundary() as tx:
            network = self._networks.require_ready(actor, network_id)
            if original is not None and self._stored(actor, network_id, original.id).status in {
                "deleting",
                "deleted",
            }:
                raise ServiceError(ErrorCode.CONFLICT)
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
        if original.status in {"deleting", "deleted"} or original.manifest is None:
            raise ServiceError(ErrorCode.CONFLICT)
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
        fatal = (
            not nodes
            or not statuses
            or any(status in {"FAILED", "UNKNOWN", "UNSUPPORTED"} for status in statuses)
            or any(item.get("Type") in {"Parse error", "Convert error"} for item in answer.issues)
        )
        warnings = any(status != "PASSED" for status in statuses) or bool(
            answer.issues or answer.parse_warnings or answer.conversion_warnings
        )
        status = "failed" if fatal else "ready_with_warnings" if warnings else "ready"
        formats = sorted({str(item.get("File_Format", "UNKNOWN")) for item in answer.parse_status})
        limits = []
        for vendor in ("HUAWEI_VRP", "H3C_COMWARE"):
            if vendor in formats:
                for capability in ("ipv6", "srv6", "evpn", "acl"):
                    limits.append(
                        {
                            "vendor": vendor,
                            "capability": capability,
                            "status": "unknown" if capability == "acl" else "unsupported",
                            "description": "当前模型不能据此证明IPv6、SRv6、EVPN转发或ACL策略正确；解析PASSED不表示完整模拟。",
                        }
                    )
        return status, {
            "file_count": len(statuses),
            "node_count": len(nodes),
            "issue_count": len(answer.issues),
            "parse_statuses": sorted(set(statuses)),
            "file_formats": formats,
            "model_limits": limits,
            "coverage": "unknown"
            if fatal or "UNKNOWN" in formats
            else "limited"
            if warnings or limits
            else "unknown",
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

    def register_derived(
        self, actor, network_id, base_snapshot_id, identifier, display_name, *, transaction
    ):
        self.require_analyzable(actor, network_id, base_snapshot_id)
        base = SnapshotsRepository(transaction).get(base_snapshot_id)
        if base is None or base.network_id != network_id or base.manifest is None:
            raise ServiceError(ErrorCode.CONFLICT)
        return SnapshotsRepository(transaction).add_derived(identifier, actor, base, display_name)

    def attach_derived_job(self, identifier, job_id, *, transaction):
        SnapshotsRepository(transaction).attach_job(identifier, job_id)

    def complete_derived(self, job, answer):
        status, quality = self.quality(answer)
        with self._database.transaction() as tx:
            SnapshotsRepository(tx).complete(job.context.snapshot_id, answer, status, quality)
        if status == "failed":
            raise ServiceError(ErrorCode.NOT_READY)

    def require_no_derived(self, snapshot_id, *, transaction):
        if SnapshotsRepository(transaction).has_live_derived(snapshot_id):
            raise ServiceError(ErrorCode.CONFLICT)

    def files(self, actor, network_id, snapshot_id):
        row = self._stored(actor, network_id, snapshot_id)
        if row.status == "deleted":
            raise ServiceError(ErrorCode.NOT_FOUND)
        return SnapshotFiles(
            items=self._uploads.describe_files(row.manifest) if row.manifest else ()
        )

    def read_file(self, actor, network_id, snapshot_id, file_id, *, offset=0, limit=50):
        row = self._stored(actor, network_id, snapshot_id)
        if row.manifest is None or row.status == "deleted":
            raise ServiceError(ErrorCode.NOT_FOUND)
        return self._uploads.read_file(row.manifest, file_id, offset=offset, limit=limit)

    def diagnostics(self, actor, network_id, snapshot_id, *, offset=0, limit=50, severity=None):
        row = self._stored(actor, network_id, snapshot_id)
        if (
            offset < 0
            or not 1 <= limit <= 200
            or severity not in {None, "info", "warning", "error"}
        ):
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        if self._present(actor, row).status in {"queued", "initializing"}:
            raise ServiceError(ErrorCode.CONFLICT)
        entries = {entry.path: entry for entry in row.manifest.files} if row.manifest else {}
        diagnostics = []
        for key, source in [
            ("parse_status", "fileParseStatus"),
            ("issues", "initIssues"),
            ("parse_warnings", "parseWarning"),
            ("conversion_warnings", "viConversionWarning"),
        ]:
            for raw in row.diagnostics.get(key, ()):
                status = raw.get("Status") if source == "fileParseStatus" else raw.get("Type")
                level = (
                    "error"
                    if status
                    in {"FAILED", "UNKNOWN", "UNSUPPORTED", "Parse error", "Convert error"}
                    else "info"
                    if source == "fileParseStatus" and status == "PASSED"
                    else "warning"
                )
                if severity is not None and severity != level:
                    continue
                locations = []
                positions = raw.get("Source_Lines") or ()
                filename = raw.get("File_Name") or raw.get("Filename")
                if filename:
                    line = raw.get("Line")
                    positions = (
                        *positions,
                        {
                            "filename": filename,
                            "lines": [line]
                            if isinstance(line, int) and not isinstance(line, bool) and line > 0
                            else [],
                        },
                    )
                for location in positions:
                    if not isinstance(location, dict) and not hasattr(location, "get"):
                        continue
                    path = location.get("filename")
                    entry = entries.get(path)
                    # Preserve only actual source positions, never infer file IDs or line 1.
                    if entry is not None:
                        lines = tuple(
                            value
                            for value in (location.get("lines") or ())
                            if isinstance(value, int) and not isinstance(value, bool) and value > 0
                        )
                        locations.append(
                            SourceLocation(file_id=entry.id, path=entry.path, lines=lines)
                        )
                diagnostics.append(
                    Diagnostic(
                        source=source,
                        severity=level,
                        status=status,
                        description=str(
                            raw.get("Details")
                            or raw.get("Comment")
                            or raw.get("Warning")
                            or status
                            or source
                        ),
                        locations=tuple(locations),
                        raw=thaw(raw),
                    )
                )
        return DiagnosticPage(
            items=tuple(diagnostics[offset : offset + limit]),
            total=len(diagnostics),
            offset=offset,
            limit=limit,
        )

    def require_empty_network(self, network_id, *, transaction):
        if SnapshotsRepository(transaction).has_live(network_id):
            raise ServiceError(ErrorCode.CONFLICT)

    def mark_deleting(self, actor, network_id, identifier, job_id, *, transaction):
        row = self._stored(actor, network_id, identifier)
        if row.status in {"deleting", "deleted"}:
            raise ServiceError(ErrorCode.CONFLICT)
        SnapshotsRepository(transaction).begin_deletion(identifier, job_id)

    def deletion_resource(self, job):
        with self._database.transaction() as tx:
            row = SnapshotsRepository(tx).get(job.context.snapshot_id)
        if (
            row is None
            or row.deletion_job_id != job.id
            or row.status not in {"deleting", "deleted"}
        ):
            raise ServiceError(ErrorCode.CONFLICT)
        return row

    def deletion_presence(self, job, *, remove=False):
        self.deletion_resource(job)
        return self._controller.deletion_presence(job.context, remove=remove)

    def finish_deletion(self, job, *, state, transaction):
        self.deletion_resource(job)
        SnapshotsRepository(transaction).finish_deletion(job.context.snapshot_id, state=state)

    def cleanup_deleted(self, job):
        with self._jobs.resource_boundary() as tx:
            row = self.deletion_resource(job)
            if (
                row.status == "deleted"
                and row.manifest
                and not SnapshotsRepository(tx).has_upload_reference(row.manifest.upload_id)
            ):
                self._uploads.release_deleted(row.manifest)
