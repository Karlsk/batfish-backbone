"""Comparison-bound differential reachability jobs."""

from dataclasses import dataclass
from uuid import UUID

from app.contracts.base import thaw
from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, ServiceError
from app.modules.analysis.service import AnalysisService
from app.modules.auth.service import AuthService
from app.modules.changes.schemas import ReachabilityDiffRequest
from app.modules.changes.service import ChangesService
from app.modules.jobs.service import JobsService
from app.modules.results.service import ResultsService
from app.modules.snapshots.service import SnapshotsService

SCHEMA_VERSION = "reachability-diff-v1"
OPERATION = "reachability-diff"


@dataclass(frozen=True)
class PreparedReachabilityDiff:
    context: object
    parameters: dict
    cache_key: str
    quality: dict
    answer: object = None
    cached_result_id: UUID | None = None


class ReachabilityDiffService:
    def __init__(
        self,
        auth: AuthService,
        changes: ChangesService,
        snapshots: SnapshotsService,
        jobs: JobsService,
        results: ResultsService,
        analysis: AnalysisService,
    ):
        self._auth, self._changes, self._snapshots = auth, changes, snapshots
        self._jobs, self._results, self._analysis = jobs, results, analysis

    def submit(
        self,
        actor,
        comparison_id: UUID,
        request: ReachabilityDiffRequest,
        *,
        idempotency_key=None,
        retry_of=None,
    ):
        actor = self._auth.revalidate_actor(actor)
        with self._jobs.resource_boundary() as tx:
            context = self._changes.context(actor, comparison_id, transaction=tx).model_copy(
                update={"schema_version": SCHEMA_VERSION}
            )
            parameters = {
                "operation": OPERATION,
                "comparison_id": str(comparison_id),
                "request": request.model_dump(mode="json"),
            }
            return self._jobs.submit(
                actor,
                "analysis",
                context,
                parameters,
                idempotency_key,
                effective_parameters=parameters,
                retry_of=retry_of,
                transaction=tx,
            )

    def execute(self, job):
        actor = self._auth.revalidate_actor(
            Actor(user_id=job.created_by, role="member", enabled=True)
        )
        if job.requested_parameters.get("operation") != OPERATION:
            raise ServiceError(ErrorCode.CONFLICT)
        comparison_id = UUID(job.requested_parameters["comparison_id"])
        with self._jobs.resource_boundary() as tx:
            context = self._changes.context(actor, comparison_id, transaction=tx).model_copy(
                update={"schema_version": SCHEMA_VERSION}
            )
            comparison = self._changes.get(actor, comparison_id)
        if context.model_dump(mode="json") != job.context.model_dump(mode="json"):
            raise ServiceError(ErrorCode.CONFLICT)
        request = ReachabilityDiffRequest.model_validate(job.effective_parameters["request"])
        parameters = {
            "operation": OPERATION,
            "comparison_id": str(comparison_id),
            "request": request.model_dump(mode="json"),
        }
        key = self._results.cache_key(
            context,
            comparison.candidate_content_hash,
            OPERATION,
            SCHEMA_VERSION,
            parameters,
            reference_hash=comparison.baseline_content_hash,
            output_limits=self._results.output_limits,
        )
        candidate = self._snapshots.get(actor, context.network_id, context.snapshot_id)
        quality = thaw(candidate.quality_summary)
        if comparison.coverage == "limited":
            quality["coverage"] = "limited"
        self._jobs.set_phase(job.id, job.lease_owner, "checking_cache")
        cached = self._results.cached(key)
        if cached:
            return PreparedReachabilityDiff(
                context, parameters, key, quality, cached_result_id=cached
            )
        self._jobs.set_phase(job.id, job.lease_owner, "dataplane_or_query")
        answer = self._analysis.run_reachability_diff(context, request)
        answer = answer.model_copy(
            update={
                "warnings": answer.warnings
                + comparison.coverage_notes
                + (
                    "SDK witness flows are examples under the selected scope, not all affected business flows",
                    "Model reachability is not a live forwarding or reverse-path proof",
                )
            }
        )
        return PreparedReachabilityDiff(context, parameters, key, quality, answer)

    def publish(self, job, value: PreparedReachabilityDiff, *, transaction):
        if value.cached_result_id is not None:
            return value.cached_result_id
        return self._results.publish(
            value.context,
            value.answer,
            parameters=value.parameters,
            quality=value.quality,
            cache_key=value.cache_key,
            transaction=transaction,
        ).id

    def retry(self, actor, job, *, idempotency_key=None):
        if job.context is None or job.requested_parameters.get("operation") != OPERATION:
            raise ServiceError(ErrorCode.CONFLICT)
        request = ReachabilityDiffRequest.model_validate(job.requested_parameters["request"])
        return self.submit(
            actor,
            UUID(job.requested_parameters["comparison_id"]),
            request,
            idempotency_key=idempotency_key,
            retry_of=job.id,
        )
