import hashlib
import json
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.contracts.base import thaw
from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.database import Database
from app.modules.audit.service import AuditService
from app.modules.auth.service import AuthService
from app.modules.business_concerns.service import BusinessConcernsService
from app.modules.changes.service import ChangesService
from app.modules.leader.briefings_repository import BriefingsRepository
from app.modules.leader.briefings_schemas import (
    Briefing,
    BriefingPage,
    CreateBriefingRequest,
    ReviseBriefingRequest,
)
from app.modules.networks.service import NetworksService
from app.modules.results.service import ResultsService
from app.modules.snapshots.service import SnapshotsService


def _hash(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class BriefingsService:
    def __init__(
        self,
        database: Database,
        auth: AuthService,
        networks: NetworksService,
        snapshots: SnapshotsService,
        changes: ChangesService,
        concerns: BusinessConcernsService,
        results: ResultsService,
    ):
        self._database = database
        self._auth = auth
        self._networks = networks
        self._snapshots = snapshots
        self._changes = changes
        self._concerns = concerns
        self._results = results

    def _freeze(self, actor: Actor, request: CreateBriefingRequest) -> dict:
        network = self._networks.get(actor, request.network_id)
        self._snapshots.require_analyzable(actor, request.network_id, request.snapshot_id)
        snapshot = self._snapshots.get(actor, request.network_id, request.snapshot_id)
        comparison = None
        if request.comparison_id is not None:
            source = self._changes.get(actor, request.comparison_id)
            if (
                source.network_id != request.network_id
                or source.candidate_snapshot_id != request.snapshot_id
            ):
                raise ServiceError(ErrorCode.CONFLICT)
            self._snapshots.require_analyzable(
                actor, request.network_id, source.baseline_snapshot_id
            )
            comparison = source.model_dump(mode="json")
        concern = None
        if request.concern_id is not None:
            mapped = self._concerns.get(actor, request.concern_id, version=request.concern_version)
            if mapped.network_id != request.network_id or mapped.archived:
                raise ServiceError(ErrorCode.CONFLICT)
            concern = mapped.model_dump(mode="json")

        sections = []
        warnings = list(comparison["coverage_notes"] if comparison else [])
        for identifier in request.result_ids:
            result = self._results.get(actor, identifier)
            context = result.context
            if (
                context.network_id != request.network_id
                or context.snapshot_id != request.snapshot_id
            ):
                raise ServiceError(ErrorCode.CONFLICT)
            if context.reference_snapshot_id is not None and (
                comparison is None
                or context.reference_snapshot_id != UUID(comparison["baseline_snapshot_id"])
            ):
                raise ServiceError(ErrorCode.CONFLICT)
            if not self._results.evidence_available(actor, identifier):
                raise ServiceError(ErrorCode.NOT_READY)
            sections.append(
                {
                    "result_id": str(result.id),
                    "kind": result.kind,
                    "schema_version": result.schema_version,
                    "effective_parameters": thaw(result.effective_parameters),
                    "summary": thaw(result.summary),
                    "warnings": list(result.warnings),
                    "coverage": result.coverage,
                    "truncated": result.truncated,
                    "truncation_reason": result.truncation_reason,
                    "engine_version": context.engine_version,
                    "sdk_version": context.sdk_version,
                    "created_at": result.created_at.isoformat(),
                }
            )
            warnings.extend(result.warnings)
            if result.truncated:
                warnings.append(f"结果 {result.id} 已截断：{result.truncation_reason}")
            if result.coverage != "complete":
                warnings.append(f"结果 {result.id} 的模型覆盖为 {result.coverage}")
        quality = thaw(snapshot.quality_summary)
        limitations = quality.get("model_limits")
        if isinstance(limitations, (list, tuple)):
            warnings.extend(str(item) for item in limitations)
        if snapshot.status == "ready_with_warnings":
            warnings.append("快照初始化含解析警告")
        return {
            "network_id": str(request.network_id),
            "network_name": network.display_name,
            "snapshot_id": str(request.snapshot_id),
            "snapshot_name": snapshot.display_name,
            "snapshot_quality": quality,
            "comparison_id": str(request.comparison_id) if request.comparison_id else None,
            "frozen_comparison": comparison,
            "concern_id": str(request.concern_id) if request.concern_id else None,
            "concern_version": request.concern_version,
            "frozen_concern": concern,
            "sections": sections,
            "warnings": list(dict.fromkeys(warnings)),
        }

    def _source_available(self, actor: Actor, frozen: dict) -> bool:
        try:
            self._networks.get(actor, UUID(frozen["network_id"]))
            self._snapshots.get(actor, UUID(frozen["network_id"]), UUID(frozen["snapshot_id"]))
            if frozen["comparison_id"] is not None:
                self._changes.get(actor, UUID(frozen["comparison_id"]))
                self._snapshots.get(
                    actor,
                    UUID(frozen["network_id"]),
                    UUID(frozen["frozen_comparison"]["baseline_snapshot_id"]),
                )
        except ServiceError as error:
            if error.code in {ErrorCode.NOT_FOUND, ErrorCode.CONFLICT}:
                return False
            raise
        return True

    def _present(self, actor: Actor, revision, archived: bool) -> Briefing:
        frozen = revision.frozen
        source_available = self._source_available(actor, frozen)
        sections = [
            {
                **section,
                "evidence_available": source_available
                and self._results.evidence_available(actor, UUID(section["result_id"])),
            }
            for section in frozen["sections"]
        ]
        return Briefing.model_validate(
            {
                **frozen,
                "sections": sections,
                "id": revision.id,
                "report_id": revision.report_id,
                "version": revision.version,
                "title": revision.title,
                "notes": revision.notes,
                "created_by": revision.created_by,
                "created_at": revision.created_at,
                "archived": archived,
                "source_available": source_available,
            }
        )

    def _by_key(self, actor: Actor, key: str, digest: str) -> Briefing | None:
        with self._database.transaction() as tx:
            repository = BriefingsRepository(tx)
            revision = repository.by_key(actor.user_id, key)
            if revision is None:
                return None
            if revision.request_hash != digest:
                raise ServiceError(ErrorCode.CONFLICT)
            report = repository.report(revision.report_id)
        return self._present(actor, revision, report.archived)

    def create(
        self,
        actor: Actor,
        request: CreateBriefingRequest,
        *,
        idempotency_key: str,
        request_id: UUID,
    ) -> Briefing:
        actor = self._auth.revalidate_actor(actor)
        digest = _hash({"action": "create", "body": request.model_dump(mode="json")})
        previous = self._by_key(actor, idempotency_key, digest)
        if previous is not None:
            return previous
        frozen = self._freeze(actor, request)
        try:
            with self._database.transaction() as tx:
                revision = BriefingsRepository(tx).create(
                    actor_id=actor.user_id,
                    network_id=request.network_id,
                    title=request.title,
                    notes=request.notes,
                    frozen=frozen,
                    key=idempotency_key,
                    request_hash=digest,
                )
                AuditService().record(
                    transaction=tx,
                    actor_id=actor.user_id,
                    action="leader_briefing.create",
                    resource_id=revision.report_id,
                    outcome="created",
                    request_id=request_id,
                )
        except IntegrityError:
            previous = self._by_key(actor, idempotency_key, digest)
            if previous is not None:
                return previous
            raise ServiceError(ErrorCode.CONFLICT) from None
        return self._present(actor, revision, False)

    def get(self, actor: Actor, identifier: UUID) -> Briefing:
        actor = self._auth.revalidate_actor(actor)
        with self._database.transaction() as tx:
            repository = BriefingsRepository(tx)
            revision = repository.revision(identifier)
            if revision is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            report = repository.report(revision.report_id)
        return self._present(actor, revision, report.archived)

    def list(
        self,
        actor: Actor,
        *,
        network_id: UUID | None,
        include_archived: bool,
        offset: int,
        limit: int,
    ) -> BriefingPage:
        actor = self._auth.revalidate_actor(actor)
        if offset < 0 or not 1 <= limit <= 100:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        with self._database.transaction() as tx:
            repository = BriefingsRepository(tx)
            rows, total = repository.list(
                network_id=network_id,
                include_archived=include_archived,
                offset=offset,
                limit=limit,
            )
            pairs = [(row, repository.report(row.report_id).archived) for row in rows]
        return BriefingPage(
            items=tuple(self._present(actor, row, archived) for row, archived in pairs),
            offset=offset,
            limit=limit,
            total=total,
        )

    def revise(
        self,
        actor: Actor,
        identifier: UUID,
        request: ReviseBriefingRequest,
        *,
        idempotency_key: str,
        request_id: UUID,
    ) -> Briefing:
        actor = self._auth.revalidate_actor(actor)
        digest = _hash(
            {"action": "revise", "id": str(identifier), "body": request.model_dump(mode="json")}
        )
        previous = self._by_key(actor, idempotency_key, digest)
        if previous is not None:
            return previous
        try:
            with self._database.transaction() as tx:
                repository = BriefingsRepository(tx)
                current = repository.revision(identifier)
                if current is None:
                    raise ServiceError(ErrorCode.NOT_FOUND)
                report = repository.report(current.report_id, lock=True)
                if (
                    report.archived
                    or report.latest_version != request.expected_version
                    or current.version != request.expected_version
                ):
                    raise ServiceError(ErrorCode.CONFLICT)
                changed = request.model_fields_set
                revision = repository.revise(
                    report=report,
                    actor_id=actor.user_id,
                    title=request.title if "title" in changed else current.title,
                    notes=request.notes if "notes" in changed else current.notes,
                    frozen=current.frozen,
                    key=idempotency_key,
                    request_hash=digest,
                )
                AuditService().record(
                    transaction=tx,
                    actor_id=actor.user_id,
                    action="leader_briefing.revise",
                    resource_id=report.id,
                    outcome="revised",
                    request_id=request_id,
                )
        except IntegrityError:
            previous = self._by_key(actor, idempotency_key, digest)
            if previous is not None:
                return previous
            raise ServiceError(ErrorCode.CONFLICT) from None
        return self._present(actor, revision, False)

    def archive(self, actor: Actor, identifier: UUID, *, request_id: UUID) -> Briefing:
        actor = self._auth.revalidate_actor(actor)
        if actor.role != "admin":
            raise ServiceError(ErrorCode.FORBIDDEN)
        with self._database.transaction() as tx:
            repository = BriefingsRepository(tx)
            revision = repository.revision(identifier)
            if revision is None:
                raise ServiceError(ErrorCode.NOT_FOUND)
            report = repository.report(revision.report_id, lock=True)
            if not report.archived:
                report.archived = True
                AuditService().record(
                    transaction=tx,
                    actor_id=actor.user_id,
                    action="leader_briefing.archive",
                    resource_id=report.id,
                    outcome="archived",
                    request_id=request_id,
                )
        return self._present(actor, revision, True)
