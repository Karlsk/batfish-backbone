"""Phase-two acceptance on one fixed-engine, configuration-only snapshot."""

import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from app.infrastructure.sdk import SessionFactory
from app.infrastructure.settings import Settings
from tests import test_networks
from tests.integration.test_mvp_acceptance import canonical, sdk_json
from tests.test_filters import analyze
from tests.test_inventory import initialize
from tests.test_topology import protocol_files, submit_graph

phase_two_app = test_networks.network_app


def phase_two_files():
    files = []
    for name, content in protocol_files():
        if name == "c1.cfg":
            content = content.replace(
                b"neighbor 172.20.12.2 remote-as 65000",
                b"neighbor 172.20.12.2 remote-as 65001",
            )
        if name == "c2.cfg":
            content = content.replace(
                b"end",
                b"""ip access-list extended WEB-TEST
 permit ip host 10.64.0.1 host 10.64.0.2
 deny ip host 10.64.0.1 host 10.64.0.4
!
object-group network EMPTY-GROUP
!
ip access-list extended WEB-SEARCH
 permit ip host 10.64.0.1 host 10.64.0.2
 deny ip any any
 permit ip object-group EMPTY-GROUP any
 permit ip host 10.64.0.1 host 10.64.0.4
!
end""",
            )
        files.append((name, content))
    return files


def scoped(name):
    return {"mode": "literal", "values": [name]}


@pytest.mark.integration
def test_phase_two_same_snapshot_matches_sdk_and_preserves_limits(phase_two_app):
    state = initialize(phase_two_app, files=phase_two_files())
    client, db, app, headers, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    sessions = SessionFactory(
        db, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    )

    graph_result, graph, _ = submit_graph(state, {})
    with sessions.for_job(context) as session:
        direct_edges = sdk_json(
            session.q.layer3Edges().answer(snapshot=context.engine_snapshot).dict()
        )["answerElements"][0]["rows"]
    assert graph_result["kind"] == "graph" and graph["source"] == "layer3Edges"
    assert canonical(edge["properties"] for edge in graph["edges"]) == canonical(direct_edges)
    assert "isolated" in {node["id"] for node in graph["nodes"]}
    assert not any("isolated" in (edge["source"], edge["target"]) for edge in graph["edges"])

    bgp_result, bgp = analyze(state, "bgp-sessions", {})
    with sessions.for_job(context) as session:
        direct_bgp = sdk_json(
            session.q.bgpSessionStatus().answer(snapshot=context.engine_snapshot).dict()
        )["answerElements"][0]["rows"]
    assert canonical(bgp["rows"]) == canonical(direct_bgp)
    assert any(
        row["Node"]["name"] == "c1"
        and "172.20.12.2" in json.dumps(row["Remote_IP"])
        and row["Established_Status"] == "NOT_COMPATIBLE"
        for row in bgp["rows"]
    )
    assert any("model" in warning.lower() for warning in bgp_result["warnings"])

    base = {"nodes": scoped("c2"), "filters": scoped("WEB-TEST"), "source_ip": "10.64.0.1"}
    for destination, expected_action, implicit in (
        ("10.64.0.2", "PERMIT", False),
        ("10.64.0.4", "DENY", False),
        ("10.64.0.3", "DENY", True),
    ):
        result, page = analyze(state, "test-filters", base | {"destination_ip": destination})
        assert page["rows"][0]["Action"] == expected_action
        assert page["rows"][0]["Implicit_Deny"] is implicit
        assert result["context"]["snapshot_id"] == snapshot
        assert any("not end-to-end" in warning for warning in result["warnings"])

    _, unreachable = analyze(
        state,
        "filter-line-reachability",
        {"nodes": scoped("c2"), "filters": scoped("WEB-SEARCH")},
    )
    assert {"BLOCKING_LINES", "INDEPENDENTLY_UNMATCHABLE"} <= {
        row["Reason"] for row in unreachable["rows"]
    }

    dedicated = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/nodes",
        json={},
        headers=headers,
    )
    expert = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/query",
        json={"question_id": "nodes", "parameters": {}},
        headers=headers,
    )
    assert dedicated.status_code == expert.status_code == 202
    assert app.state.execution_service.run_once("worker")
    assert app.state.execution_service.run_once("worker")
    one = app.state.jobs_service.get(actor, UUID(dedicated.json()["id"]))
    two = app.state.jobs_service.get(actor, UUID(expert.json()["id"]))
    assert one.status == two.status == "succeeded"
    assert one.result_id == two.result_id
    assert one.effective_parameters == two.effective_parameters
    bad = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/query",
        json={"question_id": "__import__", "parameters": {}},
        headers=headers,
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["field_errors"][0]["path"] == ["body", "question_id"]
