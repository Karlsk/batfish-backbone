"""Leader checks are durable wrappers around registered work, never SDK calls in HTTP."""

from concurrent.futures import ThreadPoolExecutor
from time import sleep
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.modules.leader.checks_schemas import CreateCheckRunRequest
from tests import test_networks
from tests.test_auth import ORIGIN
from tests.test_comparisons import create_comparison, two_snapshots
from tests.test_inventory import initialize
from tests.test_networks import create_network
from tests.test_users import add_user, ready_user

pytestmark = pytest.mark.integration
check_app = test_networks.network_app


def test_template_catalog_is_explicit_and_rejects_unknown_template(check_app):
    client, _, _, headers = check_app
    catalog = client.get("/api/v1/leader/check-templates")
    assert catalog.status_code == 200, catalog.text
    templates = {item["id"]: item for item in catalog.json()["items"]}
    assert {
        "configuration-quality",
        "devices",
        "interfaces",
        "routes",
        "lpm-routes",
        "traceroute",
        "topology",
        "bgp",
        "acl",
        "change-config",
        "change-routes",
        "change-reachability",
        "fault",
    } <= templates.keys()
    assert templates["traceroute"]["required_scope"] == ["start_location", "destination_ip"]
    assert templates["configuration-quality"]["required_scope"] == []
    assert "network" not in templates["routes"]["options_schema"]["properties"]
    invalid = client.post(
        "/api/v1/leader/check-runs",
        headers=headers | {"Idempotency-Key": uuid4().hex},
        json={"template_id": "unknown", "network_id": str(uuid4()), "snapshot_id": str(uuid4())},
    )
    assert invalid.status_code == 422


def test_quality_run_is_frozen_idempotent_and_shared(check_app):
    state = initialize(check_app, "small_network")
    client, _, _, headers, network_id, snapshot_id, _ = state
    body = {
        "template_id": "configuration-quality",
        "network_id": network_id,
        "snapshot_id": snapshot_id,
    }
    request_headers = headers | {"Idempotency-Key": uuid4().hex}
    first = client.post("/api/v1/leader/check-runs", headers=request_headers, json=body)
    assert first.status_code == 201, first.text
    run = first.json()
    assert run["template_version"] == "1"
    assert run["status"] == "succeeded" and run["job_ids"] == []
    assert run["effective_parameters"]["snapshot_id"] == snapshot_id
    again = client.post("/api/v1/leader/check-runs", headers=request_headers, json=body)
    assert again.status_code == 201 and again.json()["id"] == run["id"]
    conflicting = client.post(
        "/api/v1/leader/check-runs",
        headers=request_headers,
        json=body | {"template_id": "devices"},
    )
    assert conflicting.status_code == 409
    assert client.get(f"/api/v1/leader/check-runs/{run['id']}").json()["id"] == run["id"]
    assert (
        client.get("/api/v1/leader/check-runs", params={"network_id": network_id}).json()["total"]
        == 1
    )
    assert add_user(client, headers, "leader-check-member").status_code == 201
    with TestClient(state[2], base_url=ORIGIN) as member:
        ready_user(member, "leader-check-member")
        assert member.get(f"/api/v1/leader/check-runs/{run['id']}").status_code == 200


def test_analysis_run_uses_worker_and_keeps_terminal_state(check_app):
    state = initialize(check_app, "small_network")
    client, database, app, headers, network_id, snapshot_id, actor = state
    key = uuid4().hex
    body = {"template_id": "devices", "network_id": network_id, "snapshot_id": snapshot_id}
    created = client.post(
        "/api/v1/leader/check-runs", headers=headers | {"Idempotency-Key": key}, json=body
    )
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["status"] == "queued" and len(run["job_ids"]) == 1
    assert app.state.execution_service.run_once("leader-check-worker")
    finished = client.get(f"/api/v1/leader/check-runs/{run['id']}")
    assert finished.status_code == 200
    assert finished.json()["status"] == "succeeded"
    assert len(finished.json()["result_ids"]) == 1
    assert app.state.jobs_service.get(actor, UUID(run["job_ids"][0])).status == "succeeded"
    assert (
        client.post(
            "/api/v1/leader/check-runs", headers=headers | {"Idempotency-Key": key}, json=body
        ).json()["id"]
        == run["id"]
    )
    with database.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM check_runs")).scalar_one() == 1


def test_scoped_mvp_templates_reject_unknown_kwargs_and_keep_range(check_app):
    client, _, app, headers, network_id, snapshot_id, _ = initialize(check_app, "small_network")
    base = {"network_id": network_id, "snapshot_id": snapshot_id}
    request_headers = headers | {"Idempotency-Key": uuid4().hex}
    missing = client.post(
        "/api/v1/leader/check-runs",
        headers=request_headers,
        json=base | {"template_id": "traceroute"},
    )
    assert missing.status_code == 422
    unknown = client.post(
        "/api/v1/leader/check-runs",
        headers=request_headers,
        json=base
        | {
            "template_id": "routes",
            "scope": {"network": "10.0.0.0/24"},
            "options": {"snapshot": "another"},
        },
    )
    assert unknown.status_code == 422
    route = client.post(
        "/api/v1/leader/check-runs",
        headers=request_headers,
        json=base | {"template_id": "routes", "scope": {"network": "10.0.0.0/24"}},
    )
    assert route.status_code == 201, route.text
    assert route.json()["effective_parameters"]["request"]["options"]["network"] == "10.0.0.0/24"
    trace = client.post(
        "/api/v1/leader/check-runs",
        headers=headers | {"Idempotency-Key": uuid4().hex},
        json=base
        | {
            "template_id": "traceroute",
            "scope": {"start_location": "r1", "destination_ip": "10.0.0.2"},
        },
    )
    assert trace.status_code == 201, trace.text
    assert trace.json()["effective_parameters"]["request"]["destination_ip"] == "10.0.0.2"
    assert app.state.execution_service.run_once("leader-scoped-worker")
    assert app.state.execution_service.run_once("leader-scoped-worker")
    assert (
        client.get(f"/api/v1/leader/check-runs/{trace.json()['id']}").json()["status"]
        == "succeeded"
    )
    lpm = client.post(
        "/api/v1/leader/check-runs",
        headers=headers | {"Idempotency-Key": uuid4().hex},
        json=base | {"template_id": "lpm-routes", "scope": {"ip": "10.0.0.2"}},
    )
    assert lpm.status_code == 201 and lpm.json()["status"] == "queued"


def test_change_and_fault_runs_freeze_direction_and_derived_snapshot(check_app):
    client, _, app, headers, network_id, baseline, candidate, _ = two_snapshots(check_app)
    comparison = create_comparison(client, headers, network_id, baseline, candidate)
    assert comparison.status_code == 201, comparison.text
    comparison_id = comparison.json()["id"]
    body = {
        "template_id": "change-config",
        "network_id": network_id,
        "snapshot_id": candidate,
        "scope": {"comparison_id": comparison_id},
    }
    key = uuid4().hex
    run = client.post(
        "/api/v1/leader/check-runs", headers=headers | {"Idempotency-Key": key}, json=body
    )
    assert run.status_code == 201, run.text
    assert run.json()["effective_parameters"]["baseline_snapshot_id"] == baseline
    assert run.json()["effective_parameters"]["candidate_snapshot_id"] == candidate
    assert (
        client.post(
            "/api/v1/leader/check-runs",
            headers=headers | {"Idempotency-Key": uuid4().hex},
            json=body | {"snapshot_id": baseline},
        ).status_code
        == 409
    )
    assert app.state.execution_service.run_once("leader-change-worker")
    assert (
        client.get(f"/api/v1/leader/check-runs/{run.json()['id']}").json()["status"] == "succeeded"
    )
    fault_body = {
        "template_id": "fault",
        "network_id": network_id,
        "snapshot_id": baseline,
        "scope": {"display_name": "c2 故障", "deactivate_nodes": ["c2"]},
    }
    fault_key = uuid4().hex
    fault = client.post(
        "/api/v1/leader/check-runs",
        headers=headers | {"Idempotency-Key": fault_key},
        json=fault_body,
    )
    assert fault.status_code == 201, fault.text
    derived = fault.json()["derived_snapshot_id"]
    assert derived and derived != baseline
    assert (
        client.post(
            "/api/v1/leader/check-runs",
            headers=headers | {"Idempotency-Key": fault_key},
            json=fault_body,
        ).json()["derived_snapshot_id"]
        == derived
    )
    assert app.state.execution_service.run_once("leader-fault-worker")
    assert (
        client.get(f"/api/v1/leader/check-runs/{fault.json()['id']}").json()["status"]
        == "succeeded"
    )
    for template_id, scope in [
        ("change-routes", {"comparison_id": comparison_id, "network": "10.64.0.0/24"}),
        (
            "change-reachability",
            {
                "comparison_id": comparison_id,
                "start_location": "c1",
                "destination_ips": "10.64.0.4",
            },
        ),
    ]:
        created = client.post(
            "/api/v1/leader/check-runs",
            headers=headers | {"Idempotency-Key": uuid4().hex},
            json={
                "template_id": template_id,
                "network_id": network_id,
                "snapshot_id": candidate,
                "scope": scope,
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["status"] == "queued"
        assert app.state.execution_service.run_once("leader-diff-worker")
        assert (
            client.get(f"/api/v1/leader/check-runs/{created.json()['id']}").json()["status"]
            == "succeeded"
        )


def test_unscoped_advance_and_acl_templates_submit_registered_jobs(check_app):
    client, _, _, headers, network_id, snapshot_id, _ = initialize(check_app, "cisco_four")
    base = {"network_id": network_id, "snapshot_id": snapshot_id}
    cases = [
        ("interfaces", {}, {}),
        ("topology", {}, {"view": "layer3"}),
        ("bgp", {}, {}),
        (
            "acl",
            {
                "source_ip": "10.64.0.1",
                "destination_ip": "10.64.0.4",
                "filters": {"mode": "literal", "values": ["WEB-TEST"]},
            },
            {},
        ),
    ]
    for template_id, scope, options in cases:
        response = client.post(
            "/api/v1/leader/check-runs",
            headers=headers | {"Idempotency-Key": uuid4().hex},
            json=base | {"template_id": template_id, "scope": scope, "options": options},
        )
        assert response.status_code == 201, (template_id, response.text)
        assert response.json()["status"] == "queued"


def test_same_key_concurrent_submission_and_interruption_do_not_replay(check_app, monkeypatch):
    client, database, app, headers, network_id, snapshot_id, actor = initialize(
        check_app, "small_network"
    )
    body = CreateCheckRunRequest(
        template_id="devices", network_id=UUID(network_id), snapshot_id=UUID(snapshot_id)
    )
    key = uuid4().hex
    dispatched = []
    original_dispatch = app.state.leader_checks_service._dispatch

    def dispatch_once(*args):
        dispatched.append(1)
        sleep(0.05)
        return original_dispatch(*args)

    monkeypatch.setattr(app.state.leader_checks_service, "_dispatch", dispatch_once)

    def submit(_):
        return app.state.leader_checks_service.create(
            actor, body, idempotency_key=key, request_id=uuid4()
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = list(pool.map(submit, range(2)))
    assert runs[0].id == runs[1].id
    assert runs[0].job_ids == runs[1].job_ids
    assert len(dispatched) == 1
    with database.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM check_runs")).scalar_one() == 1
        assert tx.execute(text("SELECT count(*) FROM jobs WHERE kind='analysis'")).scalar_one() == 1
        tx.execute(
            text(
                "UPDATE jobs SET status='running', phase='engine_wait', engine_state='unknown' WHERE id=:job"
            ),
            {"job": runs[0].job_ids[0]},
        )
    unknown = client.get(f"/api/v1/leader/check-runs/{runs[0].id}").json()
    assert unknown["status"] == "running"
    assert unknown["jobs"][0]["phase"] == "engine_wait"
    assert unknown["jobs"][0]["engine_state"] == "unknown"
    with database.transaction() as tx:
        tx.execute(
            text("UPDATE jobs SET status='interrupted', phase='interrupted' WHERE id=:job"),
            {"job": runs[0].job_ids[0]},
        )
    interrupted = client.get(f"/api/v1/leader/check-runs/{runs[0].id}").json()
    assert interrupted["status"] == "interrupted" and interrupted["result_ids"] == []
    repeat = client.post(
        "/api/v1/leader/check-runs",
        headers=headers | {"Idempotency-Key": key},
        json=body.model_dump(mode="json"),
    )
    assert repeat.status_code == 201 and repeat.json()["status"] == "interrupted"
    with database.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM jobs WHERE kind='analysis'")).scalar_one() == 1
        tx.execute(
            text("UPDATE jobs SET status='succeeded', phase='completed' WHERE id=:job"),
            {"job": runs[0].job_ids[0]},
        )
    assert (
        client.get(f"/api/v1/leader/check-runs/{runs[0].id}").json()["status"]
        == "result_unavailable"
    )


def test_concern_version_is_frozen_and_cross_network_snapshot_is_rejected(check_app):
    client, _, _, headers, network_id, snapshot_id, _ = initialize(check_app, "small_network")
    concern = client.post(
        "/api/v1/business-concerns",
        headers=headers,
        json={
            "network_id": network_id,
            "name": "Payment",
            "priority": "high",
            "flows": [{"start_location": "r1", "destination_ip": "10.0.0.2"}],
        },
    )
    assert concern.status_code == 201, concern.text
    concern_id = concern.json()["id"]
    body = {
        "template_id": "configuration-quality",
        "network_id": network_id,
        "snapshot_id": snapshot_id,
        "concern_id": concern_id,
        "concern_version": 1,
    }
    run = client.post(
        "/api/v1/leader/check-runs",
        headers=headers | {"Idempotency-Key": uuid4().hex},
        json=body,
    )
    assert run.status_code == 201, run.text
    updated = client.patch(
        f"/api/v1/business-concerns/{concern_id}",
        headers=headers,
        json={"expected_version": 1, "name": "Payment revised"},
    )
    assert updated.status_code == 200
    frozen = client.get(f"/api/v1/leader/check-runs/{run.json()['id']}").json()
    assert frozen["frozen_concern"]["name"] == "Payment"
    assert frozen["concern_version"] == 1
    second_network = create_network(client, headers).json()["id"]
    wrong = client.post(
        "/api/v1/leader/check-runs",
        headers=headers | {"Idempotency-Key": uuid4().hex},
        json=body | {"network_id": second_network},
    )
    assert wrong.status_code in {404, 409}
