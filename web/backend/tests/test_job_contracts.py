from uuid import uuid4

from app.contracts.dto import AnalysisContext, ExecutionContext
from app.modules.jobs.schemas import JobInput


def test_analysis_context_can_enter_job_submission():
    context = AnalysisContext(
        network_id=uuid4(),
        snapshot_id=uuid4(),
        engine_network="network",
        engine_snapshot="snapshot",
        engine_version="0.36.0",
        sdk_version="2026.9.17.3748",
        schema_version="1",
    )
    job = JobInput(
        kind="analysis", context=context, requested_parameters={}, effective_parameters={}
    )
    assert isinstance(job.context, ExecutionContext)
    assert job.context.model_dump() == context.model_dump()


def test_saved_frozen_parameters_can_be_resubmitted():
    context = ExecutionContext(
        network_id=uuid4(),
        engine_network="network",
        engine_version="0.36.0",
        sdk_version="2026.9.17.3748",
        schema_version="1",
    )
    first = JobInput(
        kind="analysis",
        context=context,
        requested_parameters={"options": {"nodes": ["r1"]}},
        effective_parameters={"options": {"nodes": ["r1"]}},
    )
    copied = JobInput(
        kind="analysis",
        context=context,
        requested_parameters=first.requested_parameters,
        effective_parameters=first.effective_parameters,
    )
    assert copied == first
