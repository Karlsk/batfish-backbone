from app.contracts.base import thaw
from app.contracts.dto import Actor
from app.contracts.errors import ErrorCode, FieldError, ServiceError
from app.modules.analysis.controller import AnalysisController
from app.modules.analysis.registry import Registry
from app.modules.analysis.schemas import PreparedAnalysis
from app.modules.auth.service import AuthService
from app.modules.jobs.service import JobsService
from app.modules.results.service import ResultsService
from app.modules.snapshots.service import SnapshotsService


class AnalysisService:
    @staticmethod
    def _require_acl_model(snapshot):
        quality = thaw(snapshot.quality_summary)
        if set(quality.get("file_formats", ())) & {"HUAWEI_VRP", "H3C_COMWARE"}:
            raise ServiceError(
                ErrorCode.CONFLICT,
                field_errors=(
                    FieldError(
                        path=("snapshot_id",),
                        message="ACL verification is unsupported for Huawei/H3C in this model",
                    ),
                ),
            )

    def __init__(
        self,
        auth: AuthService,
        snapshots: SnapshotsService,
        jobs: JobsService,
        results: ResultsService,
        controller: AnalysisController,
        registry: Registry,
    ):
        self._auth, self._snapshots, self._jobs = auth, snapshots, jobs
        self._results, self._controller, self._registry = results, controller, registry

    def capabilities(self, actor):
        self._auth.revalidate_actor(actor)
        return self._registry.capabilities()

    def submit(
        self,
        actor,
        network_id,
        snapshot_id,
        operation,
        request,
        *,
        idempotency_key=None,
        retry_of=None,
    ):
        actor = self._auth.revalidate_actor(actor)
        model = self._registry.validate(operation, request)
        with self._jobs.resource_boundary() as transaction:
            context = self._snapshots.require_analyzable(actor, network_id, snapshot_id)
            if operation == "test-filters":
                self._require_acl_model(self._snapshots.get(actor, network_id, snapshot_id))
            entry = self._registry.get(operation)
            context = context.model_copy(update={"schema_version": entry.schema_version})
            return self._jobs.submit(
                actor,
                "analysis",
                context,
                {
                    "operation": operation,
                    "request": model.model_dump(mode="json", exclude_unset=True),
                },
                idempotency_key,
                effective_parameters={
                    "operation": operation,
                    "request": model.model_dump(mode="json"),
                },
                retry_of=retry_of,
                transaction=transaction,
            )

    def execute(self, job):
        actor = self._auth.revalidate_actor(
            Actor(user_id=job.created_by, role="member", enabled=True)
        )
        context = self._snapshots.require_analyzable(
            actor, job.context.network_id, job.context.snapshot_id
        )
        operation = job.effective_parameters["operation"]
        entry = self._registry.get(operation)
        model = self._registry.validate(operation, job.effective_parameters["request"])
        context = context.model_copy(update={"schema_version": entry.schema_version})
        if context.model_dump(mode="json") != job.context.model_dump(mode="json"):
            raise ServiceError(ErrorCode.CONFLICT)
        versions = self._controller.runtime_versions()
        if versions != {
            "engine_version": context.engine_version,
            "sdk_version": context.sdk_version,
        }:
            # Old results remain readable, but new work must use a freshly initialized snapshot.
            raise ServiceError(
                ErrorCode.CONFLICT,
                field_errors=(
                    FieldError(
                        path=("snapshot_id",),
                        message="Runtime version changed; initialize a new snapshot before analysis",
                    ),
                ),
            )
        snapshot = self._snapshots.get(actor, context.network_id, context.snapshot_id)
        if operation == "test-filters":
            self._require_acl_model(snapshot)
        parameters = {"operation": operation, "request": model.model_dump(mode="json")}
        key = self._results.cache_key(
            context,
            snapshot.content_hash,
            operation,
            entry.schema_version,
            parameters,
            output_limits=self._results.output_limits,
        )
        self._jobs.set_phase(job.id, job.lease_owner, "checking_cache")
        cached = self._results.cached(key)
        if not cached:
            self._jobs.set_phase(
                job.id,
                job.lease_owner,
                "dataplane_or_query" if entry.requires_dataplane else "querying",
            )
        answer = (
            None
            if cached
            else self._controller.run(
                context, entry.question_id, entry.to_sdk(model), kind=entry.result_kind
            )
        )
        quality = thaw(snapshot.quality_summary)
        if (
            answer is not None
            and operation == "bgp-sessions"
            and set(quality.get("file_formats", ())) & {"HUAWEI_VRP", "H3C_COMWARE"}
        ):
            answer = answer.model_copy(
                update={
                    "warnings": answer.warnings
                    + (
                        "Huawei/H3C IPv6 BGP session behavior is not modeled; absent or ESTABLISHED rows do not establish IPv6 health",
                    ),
                }
            )
        return PreparedAnalysis(
            context,
            parameters,
            key,
            quality,
            answer=answer,
            cached_result_id=cached,
        )

    def publish(self, job, value: PreparedAnalysis, *, transaction):
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
        if job.context is None or not {"operation", "request"} <= job.requested_parameters.keys():
            raise ServiceError(ErrorCode.CONFLICT)
        return self.submit(
            actor,
            job.context.network_id,
            job.context.snapshot_id,
            job.requested_parameters["operation"],
            job.requested_parameters["request"],
            idempotency_key=idempotency_key,
            retry_of=job.id,
        )
