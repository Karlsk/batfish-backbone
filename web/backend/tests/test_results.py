from uuid import uuid4

import pytest

from tests import test_networks


def test_structured_serialization():
    from pybatfish.datamodel.primitives import FileLines

    from app.modules.analysis.controller import normalize

    value = {
        "null": float("nan"),
        "infinite": float("inf"),
        "set": {"b", "a"},
        "empty": set(),
        "source": FileLines("configs/r1.cfg", [2, 3]),
        "flow": {"ingressNode": "r1", "dstIp": "10.0.0.2"},
        "traces": [
            {
                "disposition": "ACCEPTED",
                "hops": [{"node": "r2", "steps": [{"action": "DELIVERED_TO_SUBNET"}]}],
            }
        ],
    }
    result = normalize(value)
    assert result["null"] is None and result["infinite"] is None
    assert result["set"] == ["a", "b"] and result["empty"] == []
    assert result["source"] == {"filename": "configs/r1.cfg", "lines": [2, 3]}
    assert result["traces"][0]["hops"][0]["steps"][0]["action"] == "DELIVERED_TO_SUBNET"


def test_registry_rejects_unknown_and_context_options():
    from app.contracts.errors import ServiceError
    from app.modules.analysis.registry import Registry

    registry = Registry()
    assert {item.id for item in registry.capabilities() if item.enabled} == {
        "nodes",
        "interfaces",
        "routes",
        "lpm-routes",
        "traceroute",
    }
    for request in [
        {"options": {"host": "elsewhere"}},
        {"options": {"surprise": True}},
        {"snapshot_id": str(uuid4())},
    ]:
        with pytest.raises(ServiceError) as error:
            registry.validate("nodes", request, require_enabled=False)
        assert error.value.code == "VALIDATION_ERROR" and error.value.field_errors


def test_cache_context_versions():
    from app.contracts.dto import AnalysisContext
    from app.modules.results.service import ResultsService

    context = AnalysisContext(
        network_id=uuid4(),
        snapshot_id=uuid4(),
        engine_network="network",
        engine_snapshot="snapshot",
        engine_version="engine1",
        sdk_version="sdk1",
        schema_version="1",
    )
    key = ResultsService.cache_key(
        context, "content", "nodes", "1", {"options": {"properties": ["x"]}}
    )
    for update in [
        {"snapshot_id": uuid4()},
        {"sdk_version": "sdk2"},
        {"engine_version": "engine2"},
        {"reference_snapshot_id": uuid4(), "engine_reference_snapshot": "baseline"},
    ]:
        assert (
            ResultsService.cache_key(
                context.model_copy(update=update),
                "content",
                "nodes",
                "1",
                {"options": {"properties": ["x"]}},
            )
            != key
        )
    assert (
        ResultsService.cache_key(
            context, "changed-content", "nodes", "1", {"options": {"properties": ["x"]}}
        )
        != key
    )
    assert (
        ResultsService.cache_key(
            context, "content", "nodes", "2", {"options": {"properties": ["x"]}}
        )
        != key
    )


result_app = test_networks.network_app


@pytest.mark.integration
def test_stable_pagination_and_truncation(result_app):
    from uuid import UUID

    from app.contracts.results import Column, StructuredAnswer
    from app.infrastructure.settings import Settings
    from app.modules.results.service import ResultsService
    from tests.test_snapshots import create, setup

    client, db, app, headers, network, source, actor = setup(result_app)
    created = create(client, headers, network, source).json()
    context = app.state.jobs_service.get(actor, UUID(created["job_id"])).context
    service = ResultsService(
        db,
        app.state.auth_service,
        Settings(data_dir=app.state.uploads_service.storage_root.parent, table_rows=3),
    )
    answer = StructuredAnswer(
        kind="table",
        columns=(
            Column(key="Node", label="Node", type="string"),
            Column(key="Rank", label="Rank", type="integer"),
        ),
        rows=tuple(
            {"Node": value, "Rank": rank}
            for value, rank in zip(["b", "a", "c", "d"], [2, 10, 1, 4])
        ),
    )
    with db.transaction() as tx:
        result = service.publish(
            context,
            answer,
            parameters={},
            quality={"coverage": "unknown"},
            cache_key="a" * 64,
            transaction=tx,
        )
    assert result.truncated and result.truncation_reason == "row_limit"
    first = service.rows(actor, result.id, offset=0, limit=2, sort="Node")
    second = service.rows(actor, result.id, offset=2, limit=2, sort="Node")
    assert [row["Node"] for row in (*first.rows, *second.rows)] == ["a", "b", "c"]
    assert first.total == 3 and first.truncated
    assert [row["Rank"] for row in service.rows(actor, result.id, sort="Rank").rows] == [1, 2, 10]
    assert service.cached("a" * 64) == result.id
    response = client.get("/api/v1/results/" + str(result.id))
    assert response.status_code == 200
    assert (
        client.get(
            "/api/v1/results/" + str(result.id) + "/rows", params={"sort": "unknown"}
        ).status_code
        == 422
    )


@pytest.mark.integration
def test_result_and_job_success_publish_together(result_app, monkeypatch):
    from uuid import UUID

    from sqlalchemy import text

    from app.contracts.results import Column, StructuredAnswer
    from app.infrastructure.settings import Settings
    from app.modules.execution.schemas import Handler
    from app.modules.results.service import ResultsService
    from tests.test_snapshots import create, setup

    client, db, app, headers, network, source, actor = setup(result_app)
    created = create(client, headers, network, source).json()
    context = app.state.jobs_service.get(actor, UUID(created["job_id"])).context
    app.state.jobs_service.cancel(actor, UUID(created["job_id"]))
    service = ResultsService(
        db, app.state.auth_service, Settings(data_dir=app.state.uploads_service.storage_root.parent)
    )
    answer = StructuredAnswer(
        kind="table",
        columns=(Column(key="Node", label="Node", type="string"),),
        rows=({"Node": "r1"},),
    )

    def publish(job, value, *, transaction):
        return service.publish(
            context,
            value,
            parameters={},
            quality={"coverage": "unknown"},
            cache_key="b" * 64,
            transaction=transaction,
        ).id

    app.state.execution_service._handlers["analysis"] = Handler(
        execute=lambda job: answer, publish=publish
    )
    job = app.state.jobs_service.submit(actor, "analysis", context, {})
    original = app.state.jobs_service.finish

    def fail_success(*args, **kwargs):
        if kwargs["status"] == "succeeded":
            raise RuntimeError("Injected failure between result creation and success")
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(app.state.jobs_service, "finish", fail_success)
        assert app.state.execution_service.run_once("worker")
    assert app.state.jobs_service.get(actor, job.id).status == "failed"
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM results")).scalar_one() == 0
    assert service.cached("b" * 64) is None
    again = app.state.jobs_service.submit(actor, "analysis", context, {})
    assert app.state.execution_service.run_once("worker")
    finished = app.state.jobs_service.get(actor, again.id)
    assert finished.status == "succeeded" and service.get(actor, finished.result_id)


@pytest.mark.integration
@pytest.mark.parametrize("fixture_name", ["small_network", "cisco_four"])
def test_real_result_pipeline_and_cache_identity(result_app, fixture_name, monkeypatch):
    import json
    import os
    from pathlib import Path
    from uuid import UUID

    from fastapi.testclient import TestClient

    from app.infrastructure.settings import Settings
    from app.modules.analysis.controller import AnalysisController
    from app.modules.analysis.registry import Registry
    from app.modules.analysis.schemas import Entry
    from app.modules.analysis.service import AnalysisService
    from app.modules.execution.schemas import Handler
    from tests.test_auth import ORIGIN
    from tests.test_snapshots import create, setup
    from tests.test_uploads import upload
    from tests.test_users import add_user, ready_user

    client, db, app, headers, network, source, actor = setup(result_app)
    fixture = Path(__file__).parent / "fixtures" / fixture_name / "configs"
    source = upload(
        client, headers, network, files=[(p.name, p.read_bytes()) for p in fixture.iterdir()]
    ).json()
    created = create(client, headers, network, source).json()
    assert app.state.execution_service.run_once("worker")
    manifest = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    settings = Settings(
        data_dir=app.state.uploads_service.storage_root.parent,
        batfish_host=manifest["host"],
        batfish_port=manifest["engine_port"],
    )
    calls = []

    def query(session, parameters):
        calls.append(session.network)
        return session.q.nodeProperties(**parameters)

    registry = Registry(
        [
            Entry(
                "nodes",
                "Test registered nodes",
                enabled=True,
                disabled_reason=None,
                question_id="nodeProperties",
            )
        ]
    )
    controller = AnalysisController(db, settings, queries={"nodeProperties": query})
    analysis = AnalysisService(
        app.state.auth_service,
        app.state.snapshots_service,
        app.state.jobs_service,
        app.state.results_service,
        controller,
        registry,
    )
    app.state.execution_service._handlers["analysis"] = Handler(
        analysis.execute, analysis.retry, analysis.publish
    )
    first = analysis.submit(actor, UUID(network), UUID(created["snapshot_id"]), "nodes", {})
    assert app.state.execution_service.run_once("worker")
    finished = app.state.jobs_service.get(actor, first.id)
    assert finished.status == "succeeded", finished.error
    rows = client.get("/api/v1/results/" + str(finished.result_id) + "/rows").json()
    assert rows["total"] == (2 if fixture_name == "small_network" else 4)
    assert isinstance(rows["rows"][0]["Node"], (str, dict))
    add_user(client, headers, "reader")
    with TestClient(app, base_url=ORIGIN) as other:
        ready_user(other, "reader")
        other_actor = app.state.auth_service.require_actor(other.cookies.get("batfish_session"))
        second = analysis.submit(
            other_actor, UUID(network), UUID(created["snapshot_id"]), "nodes", {}
        )
        assert app.state.execution_service.run_once("worker")
        cached = app.state.jobs_service.get(other_actor, second.id)
        assert cached.status == "succeeded" and cached.result_id == finished.result_id
        assert cached.id != finished.id and cached.created_by != finished.created_by
        assert other.get("/api/v1/results/" + str(cached.result_id)).status_code == 200
    exported = client.get(f"/api/v1/results/{finished.result_id}/export").json()
    assert exported["metadata"]["context"]["snapshot_id"] == created["snapshot_id"]
    assert len(exported["data"]["rows"]) == rows["total"]
    assert client.get(f"/api/v1/results/{finished.result_id}/export?format=csv").status_code == 200
    assert len(calls) == 1
    from pybatfish.datamodel import HeaderConstraints

    context = app.state.snapshots_service.require_analyzable(
        actor, UUID(network), UUID(created["snapshot_id"])
    )
    start, destination = (
        ("r1", "10.0.0.2") if fixture_name == "small_network" else ("c1", "10.64.0.4")
    )
    trace_controller = AnalysisController(
        db,
        settings,
        queries={
            "traceroute": lambda session, parameters: session.q.traceroute(
                startLocation=start, headers=HeaderConstraints(dstIps=destination), maxTraces=5
            )
        },
    )
    trace = trace_controller.run(context, "traceroute", {}, kind="traces")
    assert trace.rows and trace.rows[0]["Flow"]["dstIp"] == destination
    assert trace.rows[0]["Traces"][0]["hops"][0]["steps"]
    with db.transaction() as tx:
        trace_result = app.state.results_service.publish(
            context,
            trace,
            parameters={},
            quality={"coverage": "unknown"},
            cache_key=None,
            transaction=tx,
        )
    flows = app.state.results_service.flows(actor, trace_result.id)
    assert flows.items and flows.items[0].headers["dstIp"] == destination
    traces = app.state.results_service.traces(actor, trace_result.id, flows.items[0].flow_id)
    assert isinstance(traces.items[0]["hops"], tuple)
    capabilities = client.get("/api/v1/capabilities").json()
    assert len(capabilities) == 5 and {item["id"] for item in capabilities if item["enabled"]} == {
        "nodes",
        "interfaces",
        "routes",
        "lpm-routes",
        "traceroute",
    }
    changed = {"engine_version": "0.36.0", "sdk_version": "2026.9.17.3748"}
    changed["engine_version" if fixture_name == "small_network" else "sdk_version"] = "upgraded"
    monkeypatch.setattr(controller, "runtime_versions", lambda: changed, raising=False)
    incompatible = analysis.submit(actor, UUID(network), UUID(created["snapshot_id"]), "nodes", {})
    assert app.state.execution_service.run_once("worker")
    failed = app.state.jobs_service.get(actor, incompatible.id)
    assert (
        failed.status == "failed" and failed.result_id is None and failed.error.code == "CONFLICT"
    )
    assert len(calls) == 1
    assert "initialize a new snapshot" in failed.error.field_errors[0].message


@pytest.mark.integration
def test_trace_structure_and_byte_limit(result_app):
    from uuid import UUID

    from app.contracts.results import Column, StructuredAnswer
    from app.infrastructure.settings import Settings
    from app.modules.results.service import ResultsService
    from tests.test_snapshots import create, setup

    client, db, app, headers, network, source, actor = setup(result_app)
    created = create(client, headers, network, source).json()
    context = app.state.jobs_service.get(actor, UUID(created["job_id"])).context
    service = app.state.results_service
    answer = StructuredAnswer(
        kind="traces",
        columns=(),
        rows=(
            {
                "Flow": {"ingressNode": "r1", "dstIp": "10.0.0.2"},
                "Traces": [
                    {
                        "disposition": "ACCEPTED",
                        "hops": [{"node": "r2", "steps": [{"action": "ACCEPTED"}]}],
                    }
                ],
                "TraceCount": 2,
            },
        ),
    )
    with db.transaction() as tx:
        result = service.publish(
            context,
            answer,
            parameters={},
            quality={"coverage": "limited"},
            cache_key="c" * 64,
            transaction=tx,
        )
    assert result.truncated and result.truncation_reason == "trace_limit"
    base = "/api/v1/results/" + str(result.id)
    flow = client.get(base + "/flows").json()["items"][0]
    assert flow["trace_count"] == 2 and flow["returned_trace_count"] == 1 and flow["truncated"]
    traces = client.get(base + "/flows/" + flow["flow_id"] + "/traces").json()
    assert traces["items"][0]["hops"][0]["steps"][0]["action"] == "ACCEPTED"
    small = ResultsService(
        db,
        app.state.auth_service,
        Settings(data_dir=app.state.uploads_service.storage_root.parent, result_max_bytes=150),
    )
    answer = StructuredAnswer(
        kind="table",
        columns=(Column(key="value", label="Value", type="string"),),
        rows=({"value": "x" * 500},),
    )
    with db.transaction() as tx:
        limited = small.publish(
            context, answer, parameters={}, quality={}, cache_key="d" * 64, transaction=tx
        )
    assert limited.truncated and limited.truncation_reason == "byte_limit"
    assert small.rows(actor, limited.id).rows == ()


@pytest.mark.integration
def test_interruption_during_publication_cannot_publish(result_app):
    from uuid import UUID

    from sqlalchemy import text

    from app.contracts.results import StructuredAnswer
    from app.modules.execution.schemas import Handler
    from tests.test_snapshots import create, setup

    client, db, app, headers, network, source, actor = setup(result_app)
    created = create(client, headers, network, source).json()
    context = app.state.jobs_service.get(actor, UUID(created["job_id"])).context
    app.state.jobs_service.cancel(actor, UUID(created["job_id"]))
    job = app.state.jobs_service.submit(actor, "analysis", context, {})
    answer = StructuredAnswer(kind="table", columns=(), rows=())

    def publish(current, value, *, transaction):
        result = app.state.results_service.publish(
            context, value, parameters={}, quality={}, cache_key="e" * 64, transaction=transaction
        )
        # A separate transaction fences the worker before its joint success publication.
        app.state.jobs_service.interrupt(current.id, "worker")
        return result.id

    app.state.execution_service._handlers["analysis"] = Handler(
        execute=lambda job: answer, publish=publish
    )
    assert app.state.execution_service.run_once("worker")
    assert app.state.jobs_service.get(actor, job.id).status == "interrupted"
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM results")).scalar_one() == 0
    assert app.state.results_service.cached("e" * 64) is None
