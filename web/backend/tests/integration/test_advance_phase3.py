"""Phase-three acceptance: one immutable pair across all change views and a fault fork."""

import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pybatfish.datamodel import HeaderConstraints, PathConstraints

from app.infrastructure.sdk import SessionFactory
from app.infrastructure.settings import Settings
from app.modules.analysis.controller import normalize
from tests import test_networks
from tests.integration.test_mvp_acceptance import canonical, sdk_json
from tests.test_comparisons import create_comparison
from tests.test_inventory import initialize
from tests.test_snapshots import create
from tests.test_uploads import upload

pytestmark = pytest.mark.integration
phase_three_app = test_networks.network_app


def pair_files():
    folder = Path(__file__).parents[1] / "fixtures/cisco_four/configs"
    base, candidate = [], []
    for path in sorted(folder.glob("*.cfg")):
        original = path.read_bytes()
        if path.name == "c1.cfg":
            before = original.replace(b"end", b"ip route 198.51.100.0 255.255.255.0 Null0\nend")
            after = original.replace(
                b"end",
                b"""ip route 203.0.113.0 255.255.255.0 Null0
ip access-list extended BLOCK-TO-C4
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
        else:
            before = after = original
        base.append((path.name, before))
        candidate.append((path.name, after))
    return base, candidate


def complete(state, comparison, kind, body):
    client, db, app, headers, network, baseline, candidate, actor = state
    response = client.post(
        f"/api/v1/comparisons/{comparison['id']}/analyses/{kind}",
        json=body,
        headers=headers,
    )
    assert response.status_code == 202, response.text
    assert app.state.execution_service.run_once("phase-three-worker")
    job = client.get(f"/api/v1/jobs/{response.json()['id']}").json()
    assert job["status"] == "succeeded", job.get("error")
    envelope = client.get(f"/api/v1/results/{job['result_id']}").json()
    assert envelope["context"]["snapshot_id"] == candidate
    assert envelope["context"]["reference_snapshot_id"] == baseline
    return str(job["result_id"]), envelope


def test_one_pair_sdk_change_and_fault_acceptance(phase_three_app, monkeypatch):
    base_files, candidate_files = pair_files()
    state = initialize(phase_three_app, files=base_files)
    client, db, app, headers, network, baseline, actor = state
    uploaded = upload(client, headers, network, files=candidate_files).json()
    started = create(client, headers, network, uploaded, display_name="Known candidate")
    assert started.status_code == 202, started.text
    assert app.state.execution_service.run_once("phase-three-worker")
    candidate = started.json()["snapshot_id"]
    assert client.get(f"/api/v1/networks/{network}/snapshots/{candidate}").json()["status"] in {
        "ready",
        "ready_with_warnings",
    }
    state = client, db, app, headers, network, baseline, candidate, actor
    comparison_response = create_comparison(client, headers, network, baseline, candidate)
    assert comparison_response.status_code == 201, comparison_response.text
    comparison = comparison_response.json()
    assert comparison["baseline_snapshot_id"] == baseline
    assert comparison["candidate_snapshot_id"] == candidate
    assert comparison["engine_version"] and comparison["sdk_version"]
    context = app.state.changes_service.context(actor, UUID(comparison["id"]))
    manifest = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    sessions = SessionFactory(
        db, Settings(batfish_host=manifest["host"], batfish_port=manifest["engine_port"])
    )

    config_id, config_result = complete(state, comparison, "config-diff", {})
    file_page = client.get(f"/api/v1/results/{config_id}/diff/files").json()
    assert file_page["total"] == 1
    changed = file_page["items"][0]
    assert changed["path"] == "configs/c1.cfg" and changed["change"] == "changed"
    assert changed["baseline_sha256"] == hashlib.sha256(base_files[0][1]).hexdigest()
    assert changed["candidate_sha256"] == hashlib.sha256(candidate_files[0][1]).hexdigest()
    hunks = client.get(f"/api/v1/results/{config_id}/diff/files/{changed['file_id']}").json()
    assert any(
        line["text"] == "ip route 203.0.113.0 255.255.255.0 Null0"
        for hunk in hunks["hunks"]
        for line in hunk["candidate_lines"]
    )
    assert all(hunk["baseline_start"] >= 1 for hunk in hunks["hunks"])

    route_id, route_result = complete(
        state,
        comparison,
        "routes-diff",
        {"nodes": {"mode": "literal", "values": ["c1"]}, "options": {"protocols": ["static"]}},
    )
    routes = client.get(f"/api/v1/results/{route_id}/rows").json()["rows"]
    with sessions.for_job(context) as session:
        sdk_routes = normalize(
            session.q.routes(nodes="c1", protocols="static")
            .answer(
                snapshot=context.engine_snapshot,
                reference_snapshot=context.engine_reference_snapshot,
            )
            .dict()
        )["answerElements"][0]["rows"]
    assert {r["Network"]: r["Change"] for r in routes} == {
        "198.51.100.0/24": "removed",
        "203.0.113.0/24": "added",
    }
    assert canonical({k: r[k] for k in ("Network", "Entry_Presence")} for r in routes) == canonical(
        {k: r[k] for k in ("Network", "Entry_Presence")} for r in sdk_routes
    )

    reach_id, reach_result = complete(
        state,
        comparison,
        "reachability-diff",
        {
            "destination_ips": "10.64.0.4",
            "start_location": "c1",
            "options": {"source_ips": "10.64.0.1", "ip_protocols": ["icmp"]},
        },
    )
    reach_rows = client.get(f"/api/v1/results/{reach_id}/rows").json()["rows"]
    with sessions.for_job(context) as session:
        sdk_reach = normalize(
            session.q.differentialReachability(
                headers=HeaderConstraints(
                    dstIps="10.64.0.4", srcIps="10.64.0.1", ipProtocols=["icmp"]
                ),
                pathConstraints=PathConstraints(startLocation="c1"),
                maxTraces=5,
            )
            .answer(
                snapshot=context.engine_snapshot,
                reference_snapshot=context.engine_reference_snapshot,
            )
            .dict()
        )["answerElements"][0]["rows"]
    assert len(reach_rows) == len(sdk_reach) == 1
    assert reach_rows[0]["Change"] == "removed"
    assert reach_rows[0]["Snapshot_Traces"] == sdk_reach[0]["Snapshot_Traces"]
    assert reach_rows[0]["Reference_Traces"] == sdk_reach[0]["Reference_Traces"]
    assert reach_result["summary"]["count_scope"] == "sdk_witness_rows_not_all_business_flows"
    assert not reach_result["truncated"]

    before = client.get(f"/api/v1/networks/{network}/snapshots/{baseline}").json()
    baseline_context = app.state.snapshots_service.require_analyzable(
        actor, UUID(network), UUID(baseline)
    )
    with sessions.for_job(baseline_context) as session:
        base_nodes_before = sdk_json(
            session.q.nodeProperties(properties="Hostname")
            .answer(snapshot=baseline_context.engine_snapshot)
            .dict()
        )["answerElements"][0]["rows"]
    fork = client.post(
        f"/api/v1/networks/{network}/snapshots/{baseline}/fault-scenarios",
        headers=headers,
        json={"display_name": "C2 outage", "deactivate_nodes": ["c2"]},
    )
    assert fork.status_code == 202, fork.text
    assert app.state.execution_service.run_once("phase-three-worker")
    derived = fork.json()["snapshot_id"]
    derived_snapshot = client.get(f"/api/v1/networks/{network}/snapshots/{derived}").json()
    assert derived_snapshot["base_snapshot_id"] == baseline
    assert derived_snapshot["status"] in {"ready", "ready_with_warnings"}
    assert client.get(f"/api/v1/networks/{network}/snapshots/{baseline}").json() == before
    with sessions.for_job(baseline_context) as session:
        base_nodes_after = sdk_json(
            session.q.nodeProperties(properties="Hostname")
            .answer(snapshot=baseline_context.engine_snapshot)
            .dict()
        )["answerElements"][0]["rows"]
    assert canonical(base_nodes_after) == canonical(base_nodes_before)

    from pybatfish.client.session import Session

    monkeypatch.setattr(Session, "fork_snapshot", lambda *args, **kwargs: None)
    failed = client.post(
        f"/api/v1/networks/{network}/snapshots/{baseline}/fault-scenarios",
        headers=headers,
        json={"display_name": "Failed fork", "deactivate_nodes": ["c3"]},
    )
    assert failed.status_code == 202, failed.text
    assert app.state.execution_service.run_once("phase-three-worker")
    failure = client.get(f"/api/v1/jobs/{failed.json()['job_id']}").json()
    assert failure["status"] == "failed" and failure["error"]["code"] == "ENGINE_QUERY_FAILED"
    assert (
        client.post(
            f"/api/v1/networks/{network}/comparisons",
            headers=headers,
            json={
                "baseline_snapshot_id": baseline,
                "candidate_snapshot_id": failed.json()["snapshot_id"],
            },
        ).status_code
        == 503
    )
    assert client.get(f"/api/v1/networks/{network}/snapshots/{baseline}").json() == before

    evidence = Path(manifest["run_directory"]) / "acceptance"
    evidence.mkdir(exist_ok=True)
    (evidence / f"phase3-{uuid4().hex}.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "network_id": network,
                "baseline_snapshot_id": baseline,
                "candidate_snapshot_id": candidate,
                "derived_snapshot_id": derived,
                "comparison_id": comparison["id"],
                "engine_version": comparison["engine_version"],
                "sdk_version": comparison["sdk_version"],
                "config_result_id": config_id,
                "route_result_id": route_id,
                "reachability_result_id": reach_id,
                "routes": {r["Network"]: r["Change"] for r in routes},
                "reachability": reach_rows[0]["Change"],
                "fault_failed_status": failure["status"],
            },
            indent=2,
        )
        + "\n"
    )
