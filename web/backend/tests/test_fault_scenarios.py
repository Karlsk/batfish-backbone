"""Real-SDK outage forks on an isolated synthetic Cisco network."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest

from app.contracts.errors import ServiceError
from app.infrastructure.engine import EngineBusy, EngineOutcomeUnknown
from app.modules.changes.schemas import FaultScenarioRequest
from tests import test_networks
from tests.test_inventory import analyze, initialize

pytestmark = pytest.mark.integration
fault_app = test_networks.network_app


def url(network, baseline):
    return f"/api/v1/networks/{network}/snapshots/{baseline}/fault-scenarios"


def submit(client, headers, network, baseline, **body):
    return client.post(url(network, baseline), headers=headers, json=body)


def test_node_and_interface_targets(fault_app):
    client, db, app, headers, network, baseline, actor = initialize(fault_app)
    bad_node = submit(
        client, headers, network, baseline, display_name="Unknown", deactivate_nodes=["absent"]
    )
    assert bad_node.status_code == 422, bad_node.text
    bad_interface = submit(
        client,
        headers,
        network,
        baseline,
        display_name="Unknown",
        deactivate_interfaces=[{"node": "c1", "interface": "NoSuchInterface"}],
    )
    assert bad_interface.status_code == 422, bad_interface.text
    assert client.get(f"/api/v1/networks/{network}/snapshots").json()["total"] == 1
    assert submit(client, headers, network, baseline, display_name="Empty").status_code == 422

    created = submit(
        client,
        headers,
        network,
        baseline,
        display_name="C1 outage",
        deactivate_nodes=["c1"],
        deactivate_interfaces=[{"node": "c2", "interface": "GigabitEthernet0/0"}],
    )
    assert created.status_code == 202, created.text
    candidate, job_id = created.json()["snapshot_id"], created.json()["job_id"]
    queued = client.get(f"/api/v1/networks/{network}/snapshots/{candidate}").json()
    assert queued["base_snapshot_id"] == baseline
    assert queued["status"] == "queued"
    assert (
        client.post(
            f"/api/v1/networks/{network}/comparisons",
            headers=headers,
            json={"baseline_snapshot_id": baseline, "candidate_snapshot_id": candidate},
        ).status_code
        == 503
    )
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(job_id))
    assert job.status == "succeeded", job.error
    ready = client.get(f"/api/v1/networks/{network}/snapshots/{candidate}").json()
    assert ready["status"] in {"ready", "ready_with_warnings"}
    assert ready["base_snapshot_id"] == baseline
    assert (
        client.post(
            f"/api/v1/networks/{network}/comparisons",
            headers=headers,
            json={"baseline_snapshot_id": baseline, "candidate_snapshot_id": candidate},
        ).status_code
        == 201
    )


def test_base_immutable_and_idempotent(fault_app):
    client, db, app, headers, network, baseline, actor = initialize(fault_app)
    before_result, before_rows = analyze(
        (client, db, app, headers, network, baseline, actor), "nodes", {}
    )
    before = client.get(f"/api/v1/networks/{network}/snapshots/{baseline}").json()
    body = {"display_name": "C3 outage", "deactivate_nodes": ["c3"]}
    keyed = {**headers, "Idempotency-Key": "fault-c3"}
    first = submit(client, keyed, network, baseline, **body)
    assert first.status_code == 202, first.text
    again = submit(client, keyed, network, baseline, **body)
    assert again.status_code == 202 and again.json() == first.json()
    changed = submit(
        client, keyed, network, baseline, display_name="Other", deactivate_nodes=["c3"]
    )
    assert changed.status_code == 409
    assert app.state.execution_service.run_once("worker")
    after = client.get(f"/api/v1/networks/{network}/snapshots/{baseline}").json()
    assert after == before
    after_result, after_rows = analyze(
        (client, db, app, headers, network, baseline, actor), "nodes", {}
    )
    assert after_rows["rows"] == before_rows["rows"]
    assert after_result["context"]["engine_snapshot"] == before_result["context"]["engine_snapshot"]
    candidate = client.get(
        f"/api/v1/networks/{network}/snapshots/{first.json()['snapshot_id']}"
    ).json()
    assert candidate["engine_name"] != before["engine_name"]
    assert candidate["base_snapshot_id"] == baseline
    assert candidate["content_hash"] == before["content_hash"]


def test_fork_failure_retains_nonready_scenario(fault_app, monkeypatch):
    client, db, app, headers, network, baseline, actor = initialize(fault_app)
    created = submit(
        client, headers, network, baseline, display_name="Failed fork", deactivate_nodes=["c1"]
    )
    assert created.status_code == 202, created.text
    monkeypatch.setattr(
        app.state.fault_scenarios_service._controller, "fork", lambda *args, **kwargs: None
    )
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(created.json()["job_id"]))
    assert job.status == "failed" and job.error is not None
    candidate = client.get(
        f"/api/v1/networks/{network}/snapshots/{created.json()['snapshot_id']}"
    ).json()
    assert candidate["status"] == "failed" and candidate["base_snapshot_id"] == baseline
    assert (
        client.post(
            f"/api/v1/networks/{network}/comparisons",
            headers=headers,
            json={
                "baseline_snapshot_id": baseline,
                "candidate_snapshot_id": created.json()["snapshot_id"],
            },
        ).status_code
        == 503
    )


def test_sdk_unconfirmed_fork_is_definitive_failure(fault_app, monkeypatch):
    from pybatfish.client.session import Session

    client, db, app, headers, network, baseline, actor = initialize(fault_app)
    created = submit(
        client, headers, network, baseline, display_name="Unconfirmed", deactivate_nodes=["c2"]
    )
    assert created.status_code == 202
    monkeypatch.setattr(Session, "fork_snapshot", lambda *args, **kwargs: None)
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(created.json()["job_id"]))
    assert job.status == "failed" and job.error.code == "ENGINE_QUERY_FAILED"
    assert (
        client.get(f"/api/v1/networks/{network}/snapshots/{created.json()['snapshot_id']}").json()[
            "status"
        ]
        == "failed"
    )


@pytest.mark.parametrize(
    "engine_error,expected_code",
    [
        (EngineBusy(), "NOT_READY"),
        (EngineBusy(unknown=True), "ENGINE_STATE_UNKNOWN"),
        (EngineOutcomeUnknown(), "ENGINE_STATE_UNKNOWN"),
    ],
)
def test_inventory_engine_busy_is_explained(fault_app, monkeypatch, engine_error, expected_code):
    client, db, app, headers, network, baseline, actor = initialize(fault_app)

    def raise_engine_error(*args):
        raise engine_error

    monkeypatch.setattr(app.state.analysis_service, "fault_targets", raise_engine_error)
    response = submit(
        client, headers, network, baseline, display_name="Busy", deactivate_nodes=["c1"]
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == expected_code
    assert client.get(f"/api/v1/networks/{network}/snapshots").json()["total"] == 1


def test_idempotent_repeat_survives_busy_inventory(fault_app, monkeypatch):
    client, db, app, headers, network, baseline, actor = initialize(fault_app)
    keyed = headers | {"Idempotency-Key": "fault-repeat-busy"}
    body = {"display_name": "Outage", "deactivate_nodes": ["c1"]}
    first = submit(client, keyed, network, baseline, **body)
    assert first.status_code == 202

    def busy(*args):
        raise EngineBusy()

    monkeypatch.setattr(app.state.analysis_service, "fault_targets", busy)
    repeated = submit(client, keyed, network, baseline, **body)
    assert repeated.status_code == 202 and repeated.json() == first.json()
    changed = submit(
        client, keyed, network, baseline, display_name="Other", deactivate_nodes=["c1"]
    )
    assert changed.status_code == 409


def test_baseline_deletion_requires_derived_deletion(fault_app):
    client, db, app, headers, network, baseline, actor = initialize(fault_app)
    created = submit(
        client, headers, network, baseline, display_name="C4 outage", deactivate_nodes=["c4"]
    )
    assert created.status_code == 202, created.text
    candidate = created.json()["snapshot_id"]
    assert (
        client.delete(
            f"/api/v1/networks/{network}/snapshots/{baseline}", headers=headers
        ).status_code
        == 409
    )
    assert app.state.execution_service.run_once("worker")
    assert (
        client.delete(
            f"/api/v1/networks/{network}/snapshots/{baseline}", headers=headers
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"/api/v1/networks/{network}/snapshots/{candidate}", headers=headers
        ).status_code
        == 202
    )
    assert app.state.execution_service.run_once("worker")
    assert (
        client.delete(
            f"/api/v1/networks/{network}/snapshots/{baseline}", headers=headers
        ).status_code
        == 202
    )


def test_create_and_delete_baseline_are_serialized(fault_app):
    client, db, app, headers, network, baseline, actor = initialize(fault_app)
    barrier = Barrier(2)

    def attempt(create):
        barrier.wait(timeout=5)
        try:
            if create:
                app.state.fault_scenarios_service.create(
                    actor,
                    UUID(network),
                    UUID(baseline),
                    FaultScenarioRequest(display_name="Race", deactivate_nodes=("c1",)),
                )
                return "created"
            app.state.lifecycle_service.delete(actor, UUID(network), UUID(baseline))
            return "deleting"
        except ServiceError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (True, False)))
    assert len(set(outcomes) & {"created", "deleting"}) == 1, outcomes
    assert any(item in {"CONFLICT", "NOT_READY"} for item in outcomes), outcomes
