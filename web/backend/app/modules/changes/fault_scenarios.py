"""Admission and worker orchestration for node/interface outage scenarios."""

import hashlib
from uuid import UUID, uuid4

from app.contracts.dto import Actor, ExecutionContext
from app.contracts.errors import ErrorCode, FieldError, ServiceError
from app.contracts.snapshots import SnapshotCreated
from app.infrastructure.engine import EngineBusy, EngineOutcomeUnknown
from app.modules.analysis.service import AnalysisService
from app.modules.auth.service import AuthService
from app.modules.changes.controller import FaultScenarioController
from app.modules.changes.schemas import FaultScenarioRequest
from app.modules.jobs.service import JobsService
from app.modules.networks.service import NetworksService
from app.modules.snapshots.service import SnapshotsService


class FaultScenariosService:
    def __init__(
        self,
        auth: AuthService,
        networks: NetworksService,
        snapshots: SnapshotsService,
        jobs: JobsService,
        analysis: AnalysisService,
        controller: FaultScenarioController,
    ):
        self._auth, self._networks, self._snapshots = auth, networks, snapshots
        self._jobs, self._analysis, self._controller = jobs, analysis, controller

    def validate_request(self, actor, request):
        self._auth.revalidate_actor(actor)
        return FaultScenarioRequest.model_validate(request)

    def create(
        self,
        actor,
        network_id: UUID,
        base_snapshot_id: UUID,
        request: FaultScenarioRequest,
        *,
        idempotency_key=None,
    ) -> SnapshotCreated:
        actor = self._auth.revalidate_actor(actor)
        resource_key = f"{network_id}:{base_snapshot_id}"
        request_hash = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        if idempotency_key is not None:
            existing = self._jobs.find_reserved_resource(
                actor,
                route="/fault-scenarios",
                resource_key=resource_key,
                key=idempotency_key,
                request_hash=request_hash,
            )
            if existing is not None:
                row = self._snapshots.get(actor, network_id, existing)
                if row.initialization_job_id is None:
                    raise ServiceError(ErrorCode.CONFLICT)
                return SnapshotCreated(snapshot_id=row.id, job_id=row.initialization_job_id)
        try:
            nodes, interfaces = self._analysis.fault_targets(actor, network_id, base_snapshot_id)
        except EngineBusy as error:
            raise ServiceError(
                ErrorCode.ENGINE_STATE_UNKNOWN if error.unknown else ErrorCode.NOT_READY,
                retryable=not error.unknown,
            ) from None
        except EngineOutcomeUnknown:
            raise ServiceError(ErrorCode.ENGINE_STATE_UNKNOWN) from None
        errors = [
            FieldError(path=("body", "deactivate_nodes", index), message="Unknown node")
            for index, name in enumerate(request.deactivate_nodes)
            if name not in nodes
        ]
        errors.extend(
            FieldError(path=("body", "deactivate_interfaces", index), message="Unknown interface")
            for index, item in enumerate(request.deactivate_interfaces)
            if (item.node, item.interface) not in interfaces
        )
        if errors:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, field_errors=tuple(errors))
        with self._jobs.resource_boundary() as tx:
            network = self._networks.require_ready(actor, network_id)
            baseline = self._snapshots.require_analyzable(actor, network_id, base_snapshot_id)
            reservation = self._jobs.reserve_resource(
                actor,
                route="/fault-scenarios",
                resource_key=resource_key,
                key=idempotency_key or uuid4().hex,
                request_hash=request_hash,
                resource_id=uuid4(),
                transaction=tx,
            )
            if not reservation.created:
                row = self._snapshots.get(actor, network_id, reservation.resource_id)
                if row.initialization_job_id is None:
                    raise ServiceError(ErrorCode.CONFLICT)
                return SnapshotCreated(snapshot_id=row.id, job_id=row.initialization_job_id)
            row = self._snapshots.register_derived(
                actor,
                network_id,
                base_snapshot_id,
                reservation.resource_id,
                request.display_name.strip(),
                transaction=tx,
            )
            context = ExecutionContext(
                network_id=network_id,
                snapshot_id=row.id,
                reference_snapshot_id=base_snapshot_id,
                engine_network=network.engine_name,
                engine_snapshot=row.engine_name,
                engine_reference_snapshot=baseline.engine_snapshot,
                engine_version=baseline.engine_version,
                sdk_version=baseline.sdk_version,
                schema_version="1",
            )
            job = self._jobs.submit(
                actor,
                "fault_scenario",
                context,
                request.model_dump(mode="json"),
                transaction=tx,
            )
            self._snapshots.attach_derived_job(row.id, job.id, transaction=tx)
            return SnapshotCreated(snapshot_id=row.id, job_id=job.id)

    def execute(self, job):
        actor = self._auth.revalidate_actor(
            Actor(user_id=job.created_by, role="member", enabled=True)
        )
        row = self._snapshots.get(actor, job.context.network_id, job.context.snapshot_id)
        if (
            row.initialization_job_id != job.id
            or row.base_snapshot_id != job.context.reference_snapshot_id
        ):
            raise ServiceError(ErrorCode.CONFLICT)
        self._snapshots.require_analyzable(
            actor, job.context.network_id, job.context.reference_snapshot_id
        )
        answer = self._controller.fork(
            job.context, FaultScenarioRequest.model_validate(job.requested_parameters)
        )
        if answer is None:
            raise ServiceError(ErrorCode.ENGINE_QUERY_FAILED)
        self._snapshots.complete_derived(job, answer)
        return None
