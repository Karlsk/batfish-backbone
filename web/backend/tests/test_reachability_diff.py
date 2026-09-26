"""Pinned SDK differential flow evidence on controlled Cisco snapshots."""

import json
import os
from pathlib import Path
from uuid import UUID

import pytest
from pybatfish.datamodel import HeaderConstraints, PathConstraints

from app.infrastructure.sdk import SessionFactory
from app.infrastructure.settings import Settings
from app.modules.analysis.controller import normalize
from app.modules.analysis.controllers.reachability import normalize_reachability_rows
from tests import test_networks
from tests.test_comparisons import create_comparison
from tests.test_inventory import initialize
from tests.test_snapshots import create
from tests.test_uploads import upload

pytestmark = pytest.mark.integration
reachability_diff_app = test_networks.network_app


def blocked_files(blocked, *, cost_change=False):
    folder = Path(__file__).parent / "fixtures/cisco_four/configs"
    files = []
    for path in sorted(folder.glob("*.cfg")):
        content = path.read_text()
        if blocked and path.name == "c1.cfg":
            content = content.replace(
                "end",
                """ip access-list extended BLOCK-TO-C4
 deny ip any host 10.64.0.4
 permit ip any any
!
interface GigabitEthernet0/0
 ip access-group BLOCK-TO-C4 out
!
interface GigabitEthernet0/1
 ip access-group BLOCK-TO-C4 out
!
end""",
            )
        if cost_change and path.name == "c1.cfg":
            content = content.replace("ip ospf cost 10", "ip ospf cost 40", 1)
        files.append((path.name, content.encode()))
    return files


def reachability_pair(
    app_fixture,
    *,
    baseline_blocked=False,
    candidate_blocked=True,
    candidate_cost_change=False,
):
    state = initialize(app_fixture, files=blocked_files(baseline_blocked))
    client, db, app, headers, network, baseline, actor = state
    source = upload(
        client,
        headers,
        network,
        files=blocked_files(candidate_blocked, cost_change=candidate_cost_change),
    ).json()
    submitted = create(client, headers, network, source, display_name="Candidate")
    assert submitted.status_code == 202, submitted.text
    assert app.state.execution_service.run_once("worker")
    candidate = submitted.json()["snapshot_id"]
    status = client.get(f"/api/v1/networks/{network}/snapshots/{candidate}").json()["status"]
    assert status in {"ready", "ready_with_warnings"}, status
    comparison = create_comparison(client, headers, network, baseline, candidate)
    assert comparison.status_code == 201, comparison.text
    return client, db, app, headers, comparison.json(), actor


def sdk_diff(state, *, max_traces=5, destination="10.64.0.4"):
    client, db, app, headers, comparison, actor = state
    context = app.state.changes_service.context(actor, UUID(comparison["id"]))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    with SessionFactory(
        db, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    ).for_job(context) as session:
        return normalize(
            session.q.differentialReachability(
                headers=HeaderConstraints(
                    dstIps=destination, srcIps="10.64.0.1", ipProtocols=["icmp"]
                ),
                pathConstraints=PathConstraints(startLocation="c1"),
                maxTraces=max_traces,
            )
            .answer(
                snapshot=context.engine_snapshot,
                reference_snapshot=context.engine_reference_snapshot,
            )
            .dict()
        )["answerElements"][0]


def submit_diff(state, body):
    client, db, app, headers, comparison, actor = state
    response = client.post(
        f"/api/v1/comparisons/{comparison['id']}/analyses/reachability-diff",
        json=body,
        headers=headers,
    )
    assert response.status_code == 202, response.text
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(response.json()["id"]))
    assert job.status == "succeeded", job.error
    result_id = str(job.result_id)
    result = client.get(f"/api/v1/results/{result_id}").json()
    rows = client.get(f"/api/v1/results/{result_id}/rows").json()
    return result, rows


SCOPED_REQUEST = {"destination_ips": "10.64.0.4", "start_location": "c1"}


def test_sdk_differential_trace_shape(reachability_diff_app):
    state = reachability_pair(reachability_diff_app)
    raw = sdk_diff(state)
    assert {item["name"] for item in raw["metadata"]["columnMetadata"]} == {
        "Flow",
        "Snapshot_Traces",
        "Snapshot_TraceCount",
        "Reference_Traces",
        "Reference_TraceCount",
    }
    assert len(raw["rows"]) == 1
    row = raw["rows"][0]
    assert row["Flow"]["dstIp"] == "10.64.0.4"
    assert {trace["disposition"] for trace in row["Snapshot_Traces"]} == {"DENIED_OUT"}
    assert {trace["disposition"] for trace in row["Reference_Traces"]} == {"ACCEPTED"}
    assert row["Snapshot_TraceCount"] >= len(row["Snapshot_Traces"]) >= 1
    assert row["Reference_TraceCount"] >= len(row["Reference_Traces"]) >= 1
    result, page = submit_diff(state, SCOPED_REQUEST)
    assert result["kind"] == "table"
    assert result["context"]["snapshot_id"] == state[4]["candidate_snapshot_id"]
    assert result["context"]["reference_snapshot_id"] == state[4]["baseline_snapshot_id"]
    assert result["summary"]["count_scope"] == "sdk_witness_rows_not_all_business_flows"
    assert page["total"] == 1
    row = page["rows"][0]
    assert row["Change"] == "removed"
    assert row["Candidate_Reachable"] is False and row["Baseline_Reachable"] is True
    assert row["Flow"]["dstIp"] == "10.64.0.4"
    assert row["Snapshot_Traces"] and row["Reference_Traces"]


def test_sdk_reverse_and_path_only_change(reachability_diff_app):
    gained_state = reachability_pair(
        reachability_diff_app, baseline_blocked=True, candidate_blocked=False
    )
    gained = sdk_diff(gained_state)["rows"]
    assert len(gained) == 1
    assert {trace["disposition"] for trace in gained[0]["Snapshot_Traces"]} == {"ACCEPTED"}
    assert {trace["disposition"] for trace in gained[0]["Reference_Traces"]} == {"DENIED_OUT"}
    result, page = submit_diff(gained_state, SCOPED_REQUEST)
    assert page["total"] == 1 and page["rows"][0]["Change"] == "added"
    assert page["rows"][0]["Candidate_Reachable"] is True
    assert page["rows"][0]["Baseline_Reachable"] is False
    path_state = reachability_pair(
        reachability_diff_app,
        baseline_blocked=False,
        candidate_blocked=False,
        candidate_cost_change=True,
    )
    path_only = sdk_diff(path_state)["rows"]
    assert path_only == []
    result, page = submit_diff(path_state, SCOPED_REQUEST)
    assert page["total"] == 0
    assert any("selected scope" in warning for warning in result["warnings"])


def test_truncated_witnesses_do_not_invent_direction(reachability_diff_app):
    state = reachability_pair(reachability_diff_app)
    raw = sdk_diff(state, max_traces=1)["rows"]
    assert len(raw) == 1
    assert raw[0]["Snapshot_TraceCount"] > len(raw[0]["Snapshot_Traces"]) == 1
    assert raw[0]["Reference_TraceCount"] > len(raw[0]["Reference_Traces"]) == 1
    result, page = submit_diff(state, SCOPED_REQUEST | {"options": {"max_traces": 1}})
    assert result["truncated"] and "trace_limit" in result["truncation_reason"]
    assert page["total"] == 1
    row = page["rows"][0]
    assert row["Evidence_Truncated"] is True
    assert row["Change"] == "undetermined"
    assert row["Snapshot_TraceCount"] > len(row["Snapshot_Traces"])
    assert row["Reference_TraceCount"] > len(row["Reference_Traces"])


def test_scope_validation_cache_export_and_history(reachability_diff_app):
    state = reachability_pair(reachability_diff_app)
    client, db, app, headers, comparison, actor = state
    endpoint = f"/api/v1/comparisons/{comparison['id']}/analyses/reachability-diff"
    for body in [
        {},
        {"start_location": "c1"},
        {"destination_ips": "", "start_location": "c1"},
        SCOPED_REQUEST | {"options": {"snapshot": "other"}},
        SCOPED_REQUEST | {"options": {"source_ips": "0.0.0.0/0"}},
        SCOPED_REQUEST | {"options": {"destination_ports": [80]}},
        SCOPED_REQUEST | {"options": {"max_traces": 0}},
    ]:
        assert client.post(endpoint, json=body, headers=headers).status_code == 422
    first = client.post(
        endpoint, json=SCOPED_REQUEST, headers=headers | {"Idempotency-Key": "reach-once"}
    )
    assert first.status_code == 202, first.text
    duplicate = client.post(
        endpoint, json=SCOPED_REQUEST, headers=headers | {"Idempotency-Key": "reach-once"}
    )
    assert duplicate.status_code == 202 and duplicate.json()["id"] == first.json()["id"]
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(first.json()["id"]))
    assert job.status == "succeeded", job.error
    cached = client.post(
        endpoint, json=SCOPED_REQUEST, headers=headers | {"Idempotency-Key": "reach-cache"}
    )
    assert cached.status_code == 202
    assert app.state.execution_service.run_once("worker")
    cached_job = app.state.jobs_service.get(actor, UUID(cached.json()["id"]))
    assert cached_job.result_id == job.result_id
    result_id = str(job.result_id)
    exported = client.get(f"/api/v1/results/{result_id}/export?format=json")
    assert exported.status_code == 200
    assert (
        exported.json()["metadata"]["context"]["reference_snapshot_id"]
        == comparison["baseline_snapshot_id"]
    )
    assert client.get(f"/api/v1/results/{result_id}/export?format=csv").status_code == 200
    assert (
        client.delete(f"/api/v1/comparisons/{comparison['id']}", headers=headers).status_code == 204
    )
    assert client.get(f"/api/v1/results/{result_id}").status_code == 200
    assert client.post(endpoint, json=SCOPED_REQUEST, headers=headers).status_code == 404


def test_partial_trace_evidence_is_conservative():
    flow = {"dstIp": "10.64.0.4"}
    rows = normalize_reachability_rows(
        [
            {
                "Flow": flow,
                "Snapshot_Traces": [{"disposition": "DENIED_OUT"}],
                "Snapshot_TraceCount": 2,
                "Reference_Traces": [{"disposition": "ACCEPTED"}],
                "Reference_TraceCount": 2,
            }
        ]
    )
    assert rows[0]["Candidate_Reachable"] is None
    assert rows[0]["Baseline_Reachable"] is True
    assert rows[0]["Change"] == "undetermined"
    assert rows[0]["Evidence_Truncated"] is True


def test_unknown_start_does_not_become_empty_success(reachability_diff_app):
    state = reachability_pair(reachability_diff_app)
    client, db, app, headers, comparison, actor = state
    response = client.post(
        f"/api/v1/comparisons/{comparison['id']}/analyses/reachability-diff",
        json=SCOPED_REQUEST | {"start_location": "missing-device"},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(response.json()["id"]))
    assert job.status == "failed" and job.result_id is None
