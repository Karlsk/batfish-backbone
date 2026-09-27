from contextlib import nullcontext
from uuid import UUID, uuid4

from app.contracts.base import thaw
from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, FieldError, ServiceError
from app.modules.audit.service import AuditService
from app.modules.auth.service import AuthService
from app.modules.changes.repository import ChangesRepository
from app.modules.changes.schemas import ComparisonPage, CreateComparisonRequest
from app.modules.jobs.service import JobsService
from app.modules.networks.service import NetworksService
from app.modules.snapshots.service import SnapshotsService


class ChangesService:
    def __init__(
        self,
        database,
        auth: AuthService,
        networks: NetworksService,
        snapshots: SnapshotsService,
        jobs: JobsService,
    ):
        self._database = database
        self._auth = auth
        self._networks = networks
        self._snapshots = snapshots
        self._jobs = jobs

    @staticmethod
    def _coverage(snapshot, label):
        notes = []
        if snapshot.status == "ready_with_warnings":
            notes.append(f"{label}: initialization has warnings")
        quality = thaw(snapshot.quality_summary)
        for item in quality.get("model_limits", ()):
            if item.get("status") != "supported":
                notes.append(
                    f"{label}: {item.get('capability', 'unknown')} model coverage is {item.get('status', 'unknown')}"
                )
        return notes

    def create(
        self, actor: Actor, network_id: UUID, request: CreateComparisonRequest, *, request_id=None
    ):
        actor = self._auth.revalidate_actor(actor)
        if request.baseline_snapshot_id == request.candidate_snapshot_id:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                field_errors=(
                    FieldError(
                        path=("body", "candidate_snapshot_id"),
                        message="Baseline and candidate must differ",
                    ),
                ),
            )
        with self._jobs.resource_boundary() as tx:
            self._networks.require_ready(actor, network_id)
            baseline_context = self._snapshots.require_analyzable(
                actor, network_id, request.baseline_snapshot_id
            )
            candidate_context = self._snapshots.require_analyzable(
                actor, network_id, request.candidate_snapshot_id
            )
            baseline = self._snapshots.get(actor, network_id, request.baseline_snapshot_id)
            candidate = self._snapshots.get(actor, network_id, request.candidate_snapshot_id)
            if (
                not baseline.engine_version
                or not baseline.sdk_version
                or baseline_context.engine_version != candidate_context.engine_version
                or baseline_context.sdk_version != candidate_context.sdk_version
            ):
                raise ServiceError(
                    ErrorCode.CONFLICT,
                    field_errors=(
                        FieldError(
                            path=("body", "candidate_snapshot_id"),
                            message="Snapshot engine or SDK versions differ",
                        ),
                    ),
                )
            name = (
                request.display_name.strip()
                if request.display_name is not None
                else f"{baseline.display_name} → {candidate.display_name}"[:255]
            )
            notes = self._coverage(baseline, "baseline") + self._coverage(candidate, "candidate")
            if thaw(baseline.quality_summary).get("file_formats") != thaw(
                candidate.quality_summary
            ).get("file_formats"):
                notes.append("Configuration formats differ between snapshots")
            record = ChangesRepository(tx).add(
                identifier=uuid4(),
                actor=actor,
                network_id=network_id,
                baseline=baseline,
                candidate=candidate,
                name=name,
                coverage="limited" if notes else "complete",
                notes=tuple(notes),
            )
            AuditService().record(
                transaction=tx,
                actor_id=actor.user_id,
                action="comparison.create",
                resource_id=record.id,
                outcome="created",
                request_id=request_id or uuid4(),
            )
            return record

    def list(self, actor: Actor, network_id: UUID, *, offset=0, limit=50) -> ComparisonPage:
        actor = self._auth.revalidate_actor(actor)
        self._networks.get(actor, network_id)
        if offset < 0 or not 1 <= limit <= 200:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as tx:
            items, total = ChangesRepository(tx).list(network_id, offset, limit)
        return ComparisonPage(items=items, offset=offset, limit=limit, total=total)

    def recent(self, actor: Actor, *, limit=5):
        self._auth.revalidate_actor(actor)
        if not 1 <= limit <= 20:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as tx:
            comparisons = ChangesRepository(tx).recent(limit)
        names = self._networks.active_names(actor, tuple(item.network_id for item in comparisons))
        return tuple(
            (item, names[item.network_id]) for item in comparisons if item.network_id in names
        )

    def get(self, actor: Actor, comparison_id: UUID):
        actor = self._auth.revalidate_actor(actor)
        with self._database.transaction() as tx:
            record = ChangesRepository(tx).get(comparison_id)
        if record is None:
            raise ServiceError(ErrorCode.NOT_FOUND)
        self._networks.get(actor, record.network_id)
        return record

    def context(self, actor: Actor, comparison_id: UUID, *, transaction=None):
        actor = self._auth.revalidate_actor(actor)
        boundary = (
            nullcontext(transaction) if transaction is not None else self._jobs.resource_boundary()
        )
        with boundary as tx:
            record = ChangesRepository(tx).get(comparison_id)
            if record is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            candidate = self._snapshots.require_analyzable(
                actor, record.network_id, record.candidate_snapshot_id
            )
            baseline = self._snapshots.require_analyzable(
                actor, record.network_id, record.baseline_snapshot_id
            )
            stored_candidate = self._snapshots.get(
                actor, record.network_id, record.candidate_snapshot_id
            )
            stored_baseline = self._snapshots.get(
                actor, record.network_id, record.baseline_snapshot_id
            )
            if (
                stored_candidate.content_hash != record.candidate_content_hash
                or stored_baseline.content_hash != record.baseline_content_hash
                or candidate.engine_version != record.candidate_engine_version
                or baseline.engine_version != record.baseline_engine_version
                or candidate.sdk_version != record.candidate_sdk_version
                or baseline.sdk_version != record.baseline_sdk_version
            ):
                raise ServiceError(ErrorCode.CONFLICT)
            return candidate.model_copy(
                update={
                    "reference_snapshot_id": baseline.snapshot_id,
                    "engine_reference_snapshot": baseline.engine_snapshot,
                }
            )

    def require_unreferenced(self, snapshot_id: UUID, *, transaction):
        if ChangesRepository(transaction).has_active_reference(snapshot_id):
            raise ServiceError(ErrorCode.CONFLICT)

    def delete(self, actor: Actor, comparison_id: UUID, *, request_id=None):
        actor = self._auth.revalidate_actor(actor)
        if actor.role != "admin":
            raise ServiceError(ErrorCode.FORBIDDEN)
        with self._jobs.resource_boundary() as tx:
            repository = ChangesRepository(tx)
            record = repository.get(comparison_id, lock=True)
            if record is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            self._networks.get(actor, record.network_id)
            for snapshot_id in (record.baseline_snapshot_id, record.candidate_snapshot_id):
                self._jobs.require_no_active(record.network_id, snapshot_id, transaction=tx)
            if not repository.soft_delete(comparison_id):
                raise ServiceError(ErrorCode.CONFLICT)
            AuditService().record(
                transaction=tx,
                actor_id=actor.user_id,
                action="comparison.delete",
                resource_id=comparison_id,
                outcome="deleted",
                request_id=request_id or uuid4(),
            )
