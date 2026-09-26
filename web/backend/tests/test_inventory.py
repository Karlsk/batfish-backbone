import json
from pathlib import Path
from uuid import UUID

import pytest

from tests import test_networks

inventory_app = test_networks.network_app


def test_inventory_options_are_typed():
    from app.contracts.errors import ServiceError
    from app.modules.analysis.registry import Registry

    registry = Registry()
    assert {c.id for c in registry.capabilities() if c.enabled} == {
        "nodes",
        "interfaces",
        "routes",
        "lpm-routes",
        "traceroute",
        "topology",
    }
    for operation, request in [
        ("nodes", {"options": {"nodes": "r1"}}),
        ("nodes", {"options": {"nodes": {"mode": "literal", "values": []}}}),
        (
            "nodes",
            {"options": {"nodes": {"mode": "literal", "values": ["r1"], "expression": ".*"}}},
        ),
        ("nodes", {"options": {"properties": ["Imaginary_Property"]}}),
        ("interfaces", {"nodes": {"mode": "expression", "expression": ""}}),
        ("interfaces", {"options": {"snapshot": "other"}}),
    ]:
        with pytest.raises(ServiceError) as error:
            registry.validate(operation, request)
        assert error.value.code == "VALIDATION_ERROR"


def initialize(app_fixture, fixture_name="cisco_four", files=None):
    from tests.test_snapshots import create, setup
    from tests.test_uploads import upload

    client, db, app, headers, network, source, actor = setup(app_fixture)
    if files is None:
        fixture = Path(__file__).parent / "fixtures" / fixture_name / "configs"
        files = [(p.name, p.read_bytes()) for p in fixture.iterdir()]
    source = upload(client, headers, network, files=files).json()
    created = create(client, headers, network, source).json()
    assert app.state.execution_service.run_once("worker")
    assert app.state.jobs_service.get(actor, UUID(created["job_id"])).status == "succeeded"
    return client, db, app, headers, network, created["snapshot_id"], actor


def analyze(state, operation, request):
    client, db, app, headers, network, snapshot, actor = state
    response = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/{operation}",
        json=request,
        headers=headers,
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert app.state.execution_service.run_once("worker")
    finished = app.state.jobs_service.get(actor, UUID(job["id"]))
    assert finished.status == "succeeded", finished.error
    result = client.get("/api/v1/results/" + str(finished.result_id)).json()
    page = client.get("/api/v1/results/" + str(finished.result_id) + "/rows").json()
    return result, page


@pytest.mark.integration
@pytest.mark.parametrize("fixture_name", ["small_network", "cisco_four"])
def test_inventory_matches_sdk(inventory_app, fixture_name):
    import os

    from app.infrastructure.sdk import SessionFactory
    from app.infrastructure.settings import Settings
    from app.modules.analysis.controller import normalize

    state = initialize(inventory_app, fixture_name)
    client, db, app, headers, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    sessions = SessionFactory(
        db, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    )
    for operation, properties in [
        ("nodes", ["Hostname", "Configuration_Format", "Interfaces"]),
        ("interfaces", ["Active", "Primary_Address", "VRF"]),
    ]:
        result, page = analyze(state, operation, {"options": {"properties": properties}})
        with sessions.for_job(context) as session:
            question = (
                session.q.nodeProperties if operation == "nodes" else session.q.interfaceProperties
            )
            raw = normalize(
                question(properties=",".join(properties))
                .answer(snapshot=context.engine_snapshot)
                .dict()
            )["answerElements"][0]
        assert {c["key"] for c in page["columns"]} == {
            c["name"] for c in raw["metadata"]["columnMetadata"]
        }

        def canonical(rows):
            return sorted(json.dumps(r, sort_keys=True) for r in rows)

        assert canonical(page["rows"]) == canonical(raw["rows"])
        assert page["total"] > 0
        if fixture_name == "small_network":
            assert result["coverage"] == "limited" and result["warnings"]
    result, page = analyze(
        state,
        "interfaces",
        {
            "nodes": {
                "mode": "literal",
                "values": ["r1" if fixture_name == "small_network" else "c1"],
            },
            "options": {"interfaces": {"mode": "literal", "values": ["Loopback0"]}},
        },
    )
    assert page["total"] == 1 and page["rows"][0]["Interface"]["interface"] == (
        "LoopBack0" if fixture_name == "small_network" else "Loopback0"
    )


@pytest.mark.integration
def test_literal_node_names(inventory_app):
    names = ["edge.+", "branch[1]", "site,a", "123-router"]
    files = [
        (
            f"r{i}.cfg",
            f"hostname {name}\ninterface Loopback0\n ip address 10.0.0.{i + 1} 255.255.255.255\n!\n".encode(),
        )
        for i, name in enumerate(names)
    ]
    state = initialize(inventory_app, files=files)
    for name in names:
        result, page = analyze(
            state, "nodes", {"options": {"nodes": {"mode": "literal", "values": [name]}}}
        )
        assert page["total"] == 1 and page["rows"][0]["Node"]["name"] == name
    result, page = analyze(
        state, "nodes", {"options": {"nodes": {"mode": "expression", "expression": "/^edge/"}}}
    )
    assert page["total"] == 1


@pytest.mark.integration
def test_no_matching_nodes(inventory_app):
    state = initialize(inventory_app)
    for operation, request in [
        ("nodes", {"options": {"nodes": {"mode": "literal", "values": ["absent"]}}}),
        ("interfaces", {"nodes": {"mode": "literal", "values": ["absent"]}}),
    ]:
        result, page = analyze(state, operation, request)
        assert page["total"] == 0 and page["rows"] == [] and page["columns"]
        assert "No matching rows" in result["warnings"]


@pytest.mark.integration
def test_inventory_api_rejects_unsafe_options_and_preserves_identity(inventory_app):
    from uuid import uuid4

    state = initialize(inventory_app)
    client, db, app, headers, network, snapshot, actor = state
    base = f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/nodes"
    assert client.post(base, json={}).status_code == 403
    for body in [
        {"options": {"host": "foreign"}},
        {"options": {"properties": ["invented"]}},
        {"options": {"nodes": {"mode": "literal", "values": []}}},
    ]:
        assert client.post(base, json=body, headers=headers).status_code == 422
    keyed = headers | {"Idempotency-Key": uuid4().hex}
    first = client.post(base, json={}, headers=keyed)
    assert first.status_code == 202
    assert client.post(base, json={}, headers=keyed).json()["id"] == first.json()["id"]
    assert (
        client.post(base, json={"options": {"properties": ["Hostname"]}}, headers=keyed).status_code
        == 409
    )
    assert (
        client.post(base.replace(snapshot, str(uuid4())), json={}, headers=headers).status_code
        == 404
    )


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["nodes", "interfaces"])
@pytest.mark.parametrize("expression", ["[", "/[/"])
def test_invalid_expression_does_not_fence_engine(inventory_app, operation, expression):
    from app.infrastructure.engine import EngineGate

    state = initialize(inventory_app)
    client, db, app, headers, network, snapshot, actor = state
    body = {"options": {operation: {"mode": "expression", "expression": expression}}}
    response = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/{operation}",
        json=body,
        headers=headers,
    )
    assert response.status_code == 202
    assert app.state.execution_service.run_once("worker")
    failed = app.state.jobs_service.get(actor, UUID(response.json()["id"]))
    assert failed.status == "failed" and failed.error.code in {
        "VALIDATION_ERROR",
        "ENGINE_QUERY_FAILED",
    }
    assert failed.error.field_errors and EngineGate(db).state() == "idle"
    assert not app.state.execution_service.stop_requested
    _, page = analyze(state, operation, {})
    assert page["total"] > 0


@pytest.mark.integration
@pytest.mark.parametrize("failure", ["transport", "work_post_rejected"])
def test_uncertain_analysis_submission_still_fences_engine(inventory_app, monkeypatch, failure):
    from pybatfish.client.session import Session
    from requests import Request, Response
    from requests.exceptions import ConnectionError, HTTPError

    from app.infrastructure.engine import EngineGate

    state = initialize(inventory_app)
    client, db, app, headers, network, snapshot, actor = state

    def fail_submission(session, **kwargs):
        if failure == "transport":
            raise ConnectionError("Synthetic lost response")
        response = Response()
        response.status_code = 400
        response.url = session.get_base_url2() + "/work"
        response.request = Request("POST", response.url).prepare()
        raise HTTPError("Synthetic work rejection without terminal observation", response=response)

    response = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/nodes", json={}, headers=headers
    )
    assert response.status_code == 202
    monkeypatch.setattr(Session, "answer_question", fail_submission)
    assert app.state.execution_service.run_once("worker")
    failed = app.state.jobs_service.get(actor, UUID(response.json()["id"]))
    assert failed.status == "interrupted" and failed.error.code == "ENGINE_STATE_UNKNOWN"
    assert EngineGate(db).state() == "unknown"


@pytest.mark.parametrize("status", ["TERMINATEDABNORMALLY", "TERMINATEDBYUSER", "ASSIGNED"])
def test_analysis_terminal_status_and_unknown_wait(status):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.contracts.errors import ServiceError
    from app.infrastructure.settings import Settings
    from app.modules.analysis.controller import AnalysisController

    session = Mock()
    session.get_work_status.return_value = {"workstatus": status}
    question = Mock()
    question.answer.return_value = "work-id"
    exited = []

    @contextmanager
    def for_job(context):
        try:
            yield session
        except BaseException:
            exited.append("unknown")
            raise
        else:
            exited.append("released")

    controller = AnalysisController(
        None, Settings(), queries={"test": lambda session, params: question}
    )
    controller._sessions = SimpleNamespace(for_job=for_job)
    controller._wait_budget = 0
    context = SimpleNamespace(engine_snapshot="snapshot", engine_reference_snapshot=None)
    with pytest.raises(TimeoutError if status == "ASSIGNED" else ServiceError):
        controller.run(context, "test", {})
    assert session.get_work_status.call_count == 1
    assert exited == (["unknown"] if status == "ASSIGNED" else ["released"])
    session.get_answer.assert_not_called()
