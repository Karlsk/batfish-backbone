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
    def fault_targets(self, actor, network_id, snapshot_id):
        """Read exact modeled names through the analysis service for fault validation."""
        actor = self._auth.revalidate_actor(actor)
        context = self._snapshots.require_analyzable(actor, network_id, snapshot_id)
        nodes = self._controller.run(
            context, "nodeProperties", {"options": {"properties": ["Hostname"], "nodes": None}}
        )
        interfaces = self._controller.run(
            context,
            "interfaceProperties",
            {"nodes": None, "options": {"properties": ["Active"], "interfaces": None}},
        )
        return (
            frozenset(row["Node"]["name"] for row in nodes.rows),
            frozenset(
                (row["Interface"]["hostname"], row["Interface"]["interface"])
                for row in interfaces.rows
            ),
        )

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

    def run_routes_diff(self, context, request):
        """Validate shared routes parameters and use the frozen two-snapshot SDK context."""
        if context.reference_snapshot_id is None or context.engine_reference_snapshot is None:
            raise ServiceError(ErrorCode.CONFLICT)
        model = self._registry.validate("routes", request)
        versions = self._controller.runtime_versions()
        if versions != {
            "engine_version": context.engine_version,
            "sdk_version": context.sdk_version,
        }:
            raise ServiceError(ErrorCode.CONFLICT)
        answer = self._controller.run(context, "routes", self._registry.get("routes").to_sdk(model))
        if not answer.rows:
            return answer.model_copy(
                update={
                    "warnings": answer.warnings + ("No route differences in the selected scope",)
                }
            )
        return answer

    def run_reachability_diff(self, context, request):
        if context.reference_snapshot_id is None or context.engine_reference_snapshot is None:
            raise ServiceError(ErrorCode.CONFLICT)
        versions = self._controller.runtime_versions()
        if versions != {
            "engine_version": context.engine_version,
            "sdk_version": context.sdk_version,
        }:
            raise ServiceError(ErrorCode.CONFLICT)
        return self._controller.run(
            context, "differentialReachability", request.model_dump(mode="json")
        )

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
        path_prefix=("body",),
    ):
        actor = self._auth.revalidate_actor(actor)
        model = self._registry.validate(operation, request, path_prefix=path_prefix)
        with self._jobs.resource_boundary() as transaction:
            context = self._snapshots.require_analyzable(actor, network_id, snapshot_id)
            if operation in {"test-filters", "search-filters", "filter-line-reachability"}:
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

    def submit_query(
        self, actor, network_id, snapshot_id, question_id, parameters, *, idempotency_key=None
    ):
        return self.submit(
            actor,
            network_id,
            snapshot_id,
            question_id,
            parameters,
            idempotency_key=idempotency_key,
            path_prefix=("body", "parameters"),
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
        if operation in {"test-filters", "search-filters", "filter-line-reachability"}:
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
