import hashlib
import json
import re
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.contracts.base import thaw
from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, FieldError, ServiceError
from app.infrastructure.database import Database
from app.modules.analysis.service import AnalysisService
from app.modules.audit.service import AuditService
from app.modules.auth.service import AuthService
from app.modules.business_concerns.service import BusinessConcernsService
from app.modules.changes.analysis import ConfigDiffService
from app.modules.changes.fault_scenarios import FaultScenariosService
from app.modules.changes.reachability_analysis import ReachabilityDiffService
from app.modules.changes.route_analysis import RouteDiffService
from app.modules.changes.service import ChangesService
from app.modules.jobs.service import JobsService
from app.modules.leader.checks_repository import CheckRunsRepository
from app.modules.leader.checks_schemas import (
    CheckRun,
    CheckRunJob,
    CheckRunPage,
    CreateCheckRunRequest,
)
from app.modules.leader.checks_templates import BY_ID, catalog
from app.modules.networks.service import NetworksService
from app.modules.snapshots.service import SnapshotsService


def _validated(model, value, *, path=("body",)):
    try:
        return model.model_validate(value)
    except ValidationError as error:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            field_errors=tuple(
                FieldError(path=(*path, *item["loc"]), message="Invalid value")
                for item in error.errors()
            ),
        ) from None


def _validated_service(validate, actor, value, *, path=("body",)):
    try:
        return validate(actor, value)
    except ValidationError as error:
        raise ServiceError(
            ErrorCode.VALIDATION_ERROR,
            field_errors=tuple(
                FieldError(path=(*path, *item["loc"]), message="Invalid value")
                for item in error.errors()
            ),
        ) from None


class CheckRunsService:
    def __init__(
        self,
        database: Database,
        auth: AuthService,
        networks: NetworksService,
        snapshots: SnapshotsService,
        concerns: BusinessConcernsService,
        analysis: AnalysisService,
        changes: ChangesService,
        config_diff: ConfigDiffService,
        route_diff: RouteDiffService,
        reachability_diff: ReachabilityDiffService,
        faults: FaultScenariosService,
        jobs: JobsService,
    ):
        self._database = database
        self._auth = auth
        self._networks = networks
        self._snapshots = snapshots
        self._concerns = concerns
        self._analysis = analysis
        self._changes = changes
        self._config_diff = config_diff
        self._route_diff = route_diff
        self._reachability_diff = reachability_diff
        self._faults = faults
        self._jobs = jobs

    def templates(self, actor: Actor):
        self._auth.revalidate_actor(actor)
        return catalog()

    def _prepare(self, actor: Actor, request: CreateCheckRunRequest):
        template = BY_ID.get(request.template_id)
        if template is None:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                field_errors=(
                    FieldError(path=("body", "template_id"), message="Unknown template"),
                ),
            )
        self._networks.get(actor, request.network_id)
        self._snapshots.require_analyzable(actor, request.network_id, request.snapshot_id)
        snapshot = self._snapshots.get(actor, request.network_id, request.snapshot_id)
        scope = _validated(template.scope_model, thaw(request.scope), path=("body", "scope"))
        options = _validated(
            template.options_model, thaw(request.options), path=("body", "options")
        )
        scope_data = scope.model_dump(mode="json", exclude_none=True)
        option_data = options.model_dump(mode="json", exclude_none=True)
        frozen_concern = None
        if request.concern_id is not None:
            concern = self._concerns.get(actor, request.concern_id, version=request.concern_version)
            if concern.network_id != request.network_id or concern.archived:
                raise ServiceError(ErrorCode.CONFLICT)
            frozen_concern = concern.model_dump(mode="json")

        effective = {"snapshot_id": str(request.snapshot_id)}
        if template.id == "configuration-quality":
            effective["quality"] = thaw(snapshot.quality_summary)
        elif template.id == "fault":
            typed = _validated_service(
                self._faults.validate_request, actor, scope_data, path=("body", "scope")
            )
            effective["request"] = typed.model_dump(mode="json")
        elif template.id.startswith("change-"):
            comparison = self._changes.get(actor, scope.comparison_id)
            if (
                comparison.network_id != request.network_id
                or comparison.candidate_snapshot_id != request.snapshot_id
            ):
                raise ServiceError(ErrorCode.CONFLICT)
            self._snapshots.require_analyzable(
                actor, request.network_id, comparison.baseline_snapshot_id
            )
            effective["comparison_id"] = str(comparison.id)
            effective["baseline_snapshot_id"] = str(comparison.baseline_snapshot_id)
            effective["candidate_snapshot_id"] = str(comparison.candidate_snapshot_id)
            if template.id == "change-config":
                typed = _validated_service(
                    self._config_diff.validate_request, actor, {"options": option_data}
                )
            elif template.id == "change-routes":
                if "network" in option_data:
                    raise ServiceError(ErrorCode.VALIDATION_ERROR)
                typed = self._analysis.validate_request(
                    actor,
                    "routes",
                    {
                        "nodes": scope_data.get("nodes"),
                        "options": option_data | {"network": scope_data["network"]},
                    },
                )
            else:
                typed = _validated_service(
                    self._reachability_diff.validate_request,
                    actor,
                    {
                        "start_location": scope_data["start_location"],
                        "destination_ips": scope_data["destination_ips"],
                        "options": option_data,
                    },
                )
            effective["request"] = typed.model_dump(mode="json")
        else:
            if template.id == "interfaces":
                analysis_request = {
                    "nodes": option_data.pop("nodes", None),
                    "options": option_data,
                }
            elif template.id == "topology":
                analysis_request = {
                    "view": option_data.pop("view", "layer3"),
                    "options": option_data,
                }
            elif template.id in {"routes", "change-routes"}:
                if "network" in option_data:
                    raise ServiceError(ErrorCode.VALIDATION_ERROR)
                analysis_request = {
                    "nodes": scope_data.get("nodes"),
                    "options": option_data | {"network": scope_data["network"]},
                }
            elif template.id == "lpm-routes":
                analysis_request = {
                    "ip": scope_data["ip"],
                    "nodes": scope_data.get("nodes"),
                    "options": option_data,
                }
            elif template.id == "traceroute":
                analysis_request = scope_data | {"options": option_data}
            elif template.id == "acl":
                analysis_request = scope_data | {"options": option_data}
            else:
                analysis_request = {"options": option_data}
            typed = self._analysis.validate_request(actor, template.capability, analysis_request)
            effective["operation"] = template.capability
            effective["request"] = typed.model_dump(mode="json")

        if frozen_concern is not None:
            effective["concern_id"] = str(request.concern_id)
            effective["concern_version"] = request.concern_version
        return template, snapshot, frozen_concern, effective

    def _present(self, stored, jobs):
        found = [jobs.get(identifier) for identifier in stored.job_ids]
        if stored.submission_state == "failed":
            status = "failed"
        elif stored.submission_state == "succeeded":
            status = "succeeded"
        elif stored.submission_state == "submitting":
            status = "submitting"
        elif not stored.job_ids:
            status = "result_unavailable"
        elif any(item is None for item in found):
            status = "result_unavailable"
        elif any(item.status == "interrupted" for item in found):
            status = "interrupted"
        elif any(item.status == "failed" for item in found):
            status = "failed"
        elif any(item.status == "cancelled" for item in found):
            status = "cancelled"
        elif any(item.status == "running" for item in found):
            status = "running"
        elif any(item.status == "queued" for item in found):
            status = "queued"
        elif any(item.kind == "analysis" and item.result_id is None for item in found):
            status = "result_unavailable"
        else:
            status = "succeeded"
        error = next((item.error for item in found if item is not None and item.error), None)
        return CheckRun(
            **stored.model_dump(
                exclude={"idempotency_key", "request_hash", "submission_state", "error_code"}
            ),
            result_ids=tuple(
                item.result_id for item in found if item is not None and item.result_id
            ),
            jobs=tuple(
                CheckRunJob(
                    id=item.id,
                    status=item.status,
                    phase=item.phase,
                    engine_state=item.engine_state,
                    result_id=item.result_id,
                    error_code=item.error.code.value if item.error else None,
                    created_at=item.created_at,
                    finished_at=item.finished_at,
                )
                for item in found
                if item is not None
            ),
            status=status,
            error=error,
            error_code=stored.error_code or (error.code.value if error else None),
        )

    def _present_many(self, actor, stored):
        ids = tuple(dict.fromkeys(identifier for row in stored for identifier in row.job_ids))
        jobs = self._jobs.get_many(actor, ids) if ids else {}
        return tuple(self._present(row, jobs) for row in stored)

    def create(
        self,
        actor: Actor,
        request: CreateCheckRunRequest,
        *,
        idempotency_key: str,
        request_id: UUID,
    ):
        actor = self._auth.revalidate_actor(actor)
        if not re.fullmatch(r"[!-~]{1,128}", idempotency_key):
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        digest = hashlib.sha256(
            json.dumps(
                request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        with self._database.transaction() as tx:
            existing = CheckRunsRepository(tx).by_key(actor.user_id, idempotency_key)
        if existing is not None:
            if existing.request_hash != digest:
                raise ServiceError(ErrorCode.CONFLICT)
            return self._finish_submission(actor, existing)
        template, snapshot, frozen_concern, effective = self._prepare(actor, request)
        identifier = uuid4()
        with self._database.transaction() as tx:
            stored, created = CheckRunsRepository(tx).reserve(
                id=identifier,
                created_by=actor.user_id,
                idempotency_key=idempotency_key,
                request_hash=digest,
                template_id=template.id,
                template_version=template.version,
                network_id=request.network_id,
                snapshot_id=request.snapshot_id,
                concern_id=request.concern_id,
                concern_version=request.concern_version,
                frozen_concern=frozen_concern,
                snapshot_quality=thaw(snapshot.quality_summary),
                engine_version=snapshot.engine_version,
                sdk_version=snapshot.sdk_version,
                effective_parameters=effective,
                job_ids=[],
                submission_state="submitting",
            )
            if stored.request_hash != digest:
                raise ServiceError(ErrorCode.CONFLICT)
            if created:
                AuditService().record(
                    transaction=tx,
                    actor_id=actor.user_id,
                    action="leader.check_run.create",
                    resource_id=stored.id,
                    outcome="created",
                    request_id=request_id,
                )
        return self._finish_submission(actor, stored)

    def _finish_submission(self, actor: Actor, stored):
        with self._database.transaction() as tx:
            repository = CheckRunsRepository(tx)
            stored = repository.lock(stored.id)
            if stored.submission_state == "submitting":
                if stored.template_id == "configuration-quality":
                    stored = repository.succeeded(stored.id)
                else:
                    try:
                        dispatched = self._dispatch(actor, stored)
                    except ServiceError as error:
                        stored = repository.failed(stored.id, error.code.value)
                    else:
                        stored = repository.dispatched(
                            stored.id,
                            job_ids=dispatched[0],
                            derived_snapshot_id=dispatched[1],
                        )
        return self._present_many(actor, (stored,))[0]

    def _dispatch(self, actor, stored):
        operation = stored.template_id
        effective = thaw(stored.effective_parameters)
        key = "leader-" + stored.id.hex
        if operation == "fault":
            created = self._faults.create(
                actor,
                stored.network_id,
                stored.snapshot_id,
                self._faults.validate_request(actor, effective["request"]),
                idempotency_key=key,
            )
            return (created.job_id,), created.snapshot_id
        if operation == "change-config":
            job = self._config_diff.submit(
                actor,
                UUID(effective["comparison_id"]),
                self._config_diff.validate_request(actor, effective["request"]),
                idempotency_key=key,
            )
        elif operation == "change-routes":
            from app.contracts.routing import RoutesRequest

            job = self._route_diff.submit(
                actor,
                UUID(effective["comparison_id"]),
                RoutesRequest.model_validate(effective["request"]),
                idempotency_key=key,
            )
        elif operation == "change-reachability":
            job = self._reachability_diff.submit(
                actor,
                UUID(effective["comparison_id"]),
                self._reachability_diff.validate_request(actor, effective["request"]),
                idempotency_key=key,
            )
        else:
            job = self._analysis.submit(
                actor,
                stored.network_id,
                stored.snapshot_id,
                effective["operation"],
                effective["request"],
                idempotency_key=key,
            )
        return (job.id,), None

    def get(self, actor: Actor, identifier: UUID) -> CheckRun:
        actor = self._auth.revalidate_actor(actor)
        with self._database.transaction() as tx:
            stored = CheckRunsRepository(tx).get(identifier)
        if stored is None:
            raise ServiceError(ErrorCode.NOT_FOUND)
        return self._present_many(actor, (stored,))[0]

    def list(
        self, actor: Actor, *, network_id: UUID | None, offset: int, limit: int
    ) -> CheckRunPage:
        actor = self._auth.revalidate_actor(actor)
        if offset < 0 or not 1 <= limit <= 100:
            raise ServiceError(ErrorCode.VALIDATION_ERROR)
        if network_id is not None:
            self._networks.get(actor, network_id)
        with self._database.transaction() as tx:
            rows, total = CheckRunsRepository(tx).list(
                network_id=network_id, offset=offset, limit=limit
            )
        return CheckRunPage(
            items=self._present_many(actor, rows), offset=offset, limit=limit, total=total
        )
