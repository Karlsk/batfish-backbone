import pytest

from app.contracts.errors import ServiceError
from app.modules.analysis.registry import Registry


def test_topology_registered_and_typed():
    registry = Registry()
    capabilities = {c.id: c for c in registry.capabilities()}
    assert "topology" in capabilities
    assert capabilities["topology"].stage == 2
    assert capabilities["topology"].result_kind == "graph"
    assert registry.validate("topology", {}).view == "layer3"
    for request in [
        {"view": "physical"},
        {"options": {"host": "other"}},
        {"options": {"nodes": "c1"}},
        {"options": {"remote_nodes": {"mode": "literal", "values": []}}},
    ]:
        with pytest.raises(ServiceError):
            registry.validate("topology", request)


def rows():
    def edge(a, ai, b, bi):
        return {
            "Interface": {"hostname": a, "interface": ai},
            "Remote_Interface": {"hostname": b, "interface": bi},
        }

    return [
        edge("a", "eth0", "b", "eth0"),
        edge("b", "eth0", "a", "eth0"),
        edge("a", "eth1", "b", "eth1"),
        edge("b", "eth2", "c", "eth0"),
    ]


def graph():
    from app.modules.analysis.controllers.topology import normalize_graph

    return normalize_graph(
        "layer3", [{"Node": {"name": n}} for n in ["a", "b", "c", "isolated"]], rows()
    )


def test_topology_edge_identity():
    from app.modules.analysis.controllers.topology import normalize_graph

    result = graph()
    assert len({e.id for e in result.edges}) == 4
    assert result == normalize_graph(
        "layer3",
        [{"Node": {"name": n}} for n in ["isolated", "c", "b", "a"]],
        list(reversed(rows())),
    )
    assert {(e.source, e.target, e.source_interface) for e in result.edges} >= {
        ("a", "b", "eth0"),
        ("b", "a", "eth0"),
        ("a", "b", "eth1"),
    }
    bgp = normalize_graph(
        "bgp",
        [],
        [
            {"Node": {"name": "a"}, "Remote_Node": {"name": "b"}, "IP": ip, "Remote_IP": "2.2.2.2"}
            for ip in ["1.1.1.1", "1.1.1.2"]
        ],
    )
    assert len({e.id for e in bgp.edges}) == 2


def test_isolated_node():
    result = graph()
    assert "isolated" in {n.id for n in result.nodes}
    assert not any(e.source == "isolated" or e.target == "isolated" for e in result.edges)


def test_graph_neighborhood_and_limits():
    from app.modules.results.graph import select_graph

    result = select_graph(graph(), focus_node="a", hops=1, limit=200)
    assert {n.id for n in result.nodes} == {"a", "b"}
    assert len(result.edges) == 3 and not result.truncated
    assert {n.id for n in select_graph(graph(), focus_node="a", hops=2, limit=200).nodes} == {
        "a",
        "b",
        "c",
    }
    assert not select_graph(graph(), focus_node="isolated", hops=0, limit=200).edges
    result = select_graph(graph(), focus_node="b", limit=1)
    assert [n.id for n in result.nodes] == ["b"] and result.truncated
    with pytest.raises(ServiceError) as error:
        select_graph(graph(), focus_node="missing")
    assert error.value.code == "NOT_FOUND"
    with pytest.raises(ServiceError):
        select_graph(graph(), limit=201)


def test_graph_storage_limits_have_no_dangling_edges():
    import json

    from app.modules.results.graph import bound_graph

    for max_items, max_bytes in [(2, 100000), (200, 500), (200, 100000)]:
        payload, reasons = bound_graph(graph(), max_items=max_items, max_bytes=max_bytes)
        assert (
            len(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            )
            <= max_bytes
        )
        nodes = {n["id"] for n in payload["nodes"]}
        assert all(e["source"] in nodes and e["target"] in nodes for e in payload["edges"])
        assert len(nodes) <= max_items and len(payload["edges"]) <= max_items
        assert bool(reasons) == (max_items == 2 or max_bytes == 500)


from tests import test_networks  # noqa: E402
from tests.integration.test_mvp_acceptance import sdk_json  # noqa: E402
from tests.test_inventory import initialize  # noqa: E402

inventory_app = test_networks.network_app


def submit_graph(state, request):
    from uuid import UUID

    client, _, app, headers, network, snapshot, actor = state
    response = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/topology",
        json=request,
        headers=headers,
    )
    assert response.status_code == 202, response.text
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(response.json()["id"]))
    assert job.status == "succeeded", job.error
    url = f"/api/v1/results/{job.result_id}"
    return client.get(url).json(), client.get(url + "/graph").json(), url


def protocol_files():
    import re
    from pathlib import Path

    files = []
    for p in sorted((Path(__file__).parent / "fixtures/cisco_four/configs").glob("*.cfg")):
        text = p.read_text()
        number = int(p.stem[1:])
        peers = []
        for ip in re.findall(r"ip address (172\.20\.\d+\.[12]) ", text):
            peers.append(ip.rsplit(".", 1)[0] + (".2" if ip.endswith(".1") else ".1"))
        text = text.replace(
            " ip ospf network point-to-point",
            " ip router isis CORE\n ip ospf network point-to-point",
        )
        extra = f"router isis CORE\n net 49.0001.0000.0000.{number:04d}.00\n is-type level-2-only\n!\nrouter bgp 65000\n bgp router-id 10.64.0.{number}\n"
        extra += "".join(f" neighbor {peer} remote-as 65000\n" for peer in peers)
        text = text.replace("end", extra + "!\nend")
        files.append((p.name, text.encode()))
    files.append(
        (
            "isolated.cfg",
            b"hostname isolated\ninterface Loopback0\n ip address 10.255.255.1 255.255.255.255\n!\n",
        )
    )
    return files


@pytest.mark.integration
@pytest.mark.parametrize("fixture_name", ["small_network", "cisco_four", "protocols"])
def test_topology_matches_sdk(inventory_app, fixture_name):
    import json
    import os
    from pathlib import Path
    from uuid import UUID

    from app.infrastructure.sdk import SessionFactory
    from app.infrastructure.settings import Settings

    state = initialize(
        inventory_app,
        fixture_name if fixture_name != "protocols" else "cisco_four",
        files=protocol_files() if fixture_name == "protocols" else None,
    )
    client, db, app, headers, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    sessions = SessionFactory(
        db, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    )
    result_ids = set()
    for view in ["layer3", "bgp", "ospf", "isis"]:
        result, page, url = submit_graph(state, {} if view == "layer3" else {"view": view})
        with sessions.for_job(context) as session:
            question = {
                "layer3": session.q.layer3Edges,
                "bgp": session.q.bgpEdges,
                "ospf": session.q.ospfEdges,
                "isis": session.q.isisEdges,
            }[view]
            # Independent SDK serialization, not the adapter's graph normalization.
            raw = sdk_json(question().answer(snapshot=context.engine_snapshot).dict())[
                "answerElements"
            ][0].get("rows", [])
            node_rows = sdk_json(
                session.q.nodeProperties(properties="Configuration_Format")
                .answer(snapshot=context.engine_snapshot)
                .dict()
            )["answerElements"][0]["rows"]
        assert sorted(json.dumps(e["properties"], sort_keys=True) for e in page["edges"]) == sorted(
            json.dumps(row, sort_keys=True) for row in raw
        )
        assert {n["id"] for n in page["nodes"]} == {row["Node"]["name"] for row in node_rows}
        assert result["kind"] == "graph" and not page["truncated"]
        assert result["id"] not in result_ids
        result_ids.add(result["id"])
        cached, _, _ = submit_graph(state, {"view": view})
        assert cached["id"] == result["id"]
        assert page["source"] == view + "Edges"
        assert result["summary"]["total_edges"] == len(raw)
        for edge in page["edges"]:
            row = edge["properties"]
            assert (edge["source"], edge["target"]) == (
                (row["Node"]["name"], row["Remote_Node"]["name"])
                if view == "bgp"
                else (row["Interface"]["hostname"], row["Remote_Interface"]["hostname"])
            )
        if fixture_name == "protocols":
            assert raw, view
            assert "isolated" in {n["id"] for n in page["nodes"]}
            assert not client.get(url + "/graph?focus_node=isolated&hops=0").json()["edges"]
        assert client.get(url + "/graph?limit=201").status_code == 422
        assert client.get(url + "/graph?focus_node=missing").status_code == 404
        assert client.get(url + "/rows").status_code == 409
        assert client.get(url + "/export?format=csv").status_code == 409
        assert client.get(url + "/export?format=json").status_code == 200
    local = "r1" if fixture_name == "small_network" else "c1"
    remote = "r2" if fixture_name == "small_network" else "c2"
    options = {
        "nodes": {"mode": "literal", "values": [local]},
        "remote_nodes": {"mode": "literal", "values": [remote]},
    }
    filtered, page, _ = submit_graph(state, {"options": options})
    assert filtered["id"] not in result_ids
    assert {n["id"] for n in page["nodes"]} == {local, remote}
    assert all(e["source"] == local and e["target"] == remote for e in page["edges"])
    assert page["edges"]


def test_topology_does_not_submit_more_work_after_budget(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.infrastructure.settings import Settings
    from app.modules.analysis.controller import AnalysisController

    clock = [0.0]
    monkeypatch.setattr("app.modules.analysis.controller.time.monotonic", lambda: clock[0])
    session = Mock()
    session.get_work_status.return_value = {"workstatus": "TERMINATEDNORMALLY"}
    session.get_answer.return_value.dict.return_value = {"answerElements": [{"rows": []}]}
    node_question, edge_question = Mock(), Mock()

    def slow_answer(**kwargs):
        clock[0] = 10.0
        return "finished-work"

    node_question.answer.side_effect = slow_answer

    @contextmanager
    def for_job(context):
        yield session

    controller = AnalysisController(
        None,
        Settings(job_wait_budget_seconds=1),
        queries={
            "nodeProperties": lambda session, parameters: node_question,
            "layer3Edges": lambda session, parameters: edge_question,
        },
    )
    controller._sessions = SimpleNamespace(for_job=for_job)
    context = SimpleNamespace(engine_snapshot="snapshot", engine_reference_snapshot=None)
    with pytest.raises(TimeoutError):
        controller.run(
            context,
            "topology",
            {"view": "layer3", "options": {"nodes": None, "remote_nodes": None}},
        )
    edge_question.answer.assert_not_called()


def test_graph_edge_only_limit_and_storage_truncation():
    from app.modules.analysis.controllers.topology import normalize_graph
    from app.modules.results.graph import select_graph

    value = normalize_graph("layer3", [], rows()[:3])
    limited = select_graph(value, limit=2)
    assert len(limited.nodes) == 2 and len(limited.edges) == 2 and limited.truncated
    assert select_graph(value, stored_truncated=True).truncated


@pytest.mark.parametrize("status", ["TERMINATEDNORMALLY", "TERMINATEDABNORMALLY", "ASSIGNED"])
def test_topology_shares_session_and_preserves_failure_gate(status, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.infrastructure.settings import Settings
    from app.modules.analysis.controller import AnalysisController

    session = Mock()
    session.get_work_status.side_effect = [
        {"workstatus": "TERMINATEDNORMALLY"},
        {"workstatus": status},
    ]
    session.get_answer.return_value.dict.return_value = {"answerElements": [{"rows": []}]}
    query = Mock()
    clock = [0.0]

    def answer(**kwargs):
        if query.answer.call_count == 2:
            clock[0] = 10.0
        return "work"

    query.answer.side_effect = answer
    monkeypatch.setattr("app.modules.analysis.controller.time.monotonic", lambda: clock[0])
    sessions, exited = [], []

    @contextmanager
    def for_job(context):
        sessions.append(session)
        try:
            yield session
        except Exception:
            exited.append("unknown")
            raise
        else:
            exited.append("released")

    observed = []

    def make_query(current, parameters):
        observed.append(current)
        return query

    controller = AnalysisController(
        None,
        Settings(job_wait_budget_seconds=1),
        queries={"nodeProperties": make_query, "layer3Edges": make_query},
    )
    controller._sessions = SimpleNamespace(for_job=for_job)
    context = SimpleNamespace(engine_snapshot="snapshot", engine_reference_snapshot=None)

    def run():
        return controller.run(
            context,
            "topology",
            {"view": "layer3", "options": {"nodes": None, "remote_nodes": None}},
        )

    if status == "TERMINATEDNORMALLY":
        assert run().kind == "graph"
    else:
        with pytest.raises(TimeoutError if status == "ASSIGNED" else ServiceError):
            run()
    assert len(sessions) == 1 and observed == [session, session]
    assert exited == (["unknown"] if status == "ASSIGNED" else ["released"])
