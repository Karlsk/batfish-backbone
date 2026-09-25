import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from tests import test_networks
from tests.test_inventory import analyze, initialize

routing_app = test_networks.network_app


def test_unsupported_address_family():
    from app.contracts.errors import ServiceError
    from app.modules.analysis.registry import Registry

    registry = Registry()
    assert registry.get("routes").enabled and registry.get("lpm-routes").enabled
    for operation, body in [
        ("routes", {"options": {"network": "2001:db8::/32"}}),
        ("routes", {"options": {"network": "10.0.0.0"}}),
        ("routes", {"options": {"network": "10.0.0.0/255.255.255.0"}}),
        ("routes", {"options": {"network": "10.0.0.0/0.0.0.255"}}),
        ("routes", {"options": {"rib": "evpn"}}),
        ("routes", {"options": {"prefix_match_type": "longest"}}),
        ("routes", {"options": {"protocols": ["invented"]}}),
        ("lpm-routes", {"ip": "2001:db8::1"}),
        ("lpm-routes", {"ip": 1}),
        ("lpm-routes", {}),
        ("lpm-routes", {"ip": "10.0.0.1", "options": {"rib": "bgp"}}),
    ]:
        with pytest.raises(ServiceError) as error:
            registry.validate(operation, body)
        assert error.value.code == "VALIDATION_ERROR"


def test_next_hop_variants():
    from pybatfish.datamodel.route import NextHopDiscard, NextHopInterface, NextHopIp, NextHopVrf

    from app.modules.analysis.controller import normalize

    values = [
        NextHopIp("192.0.2.2"),
        NextHopInterface("Ethernet0", "192.0.2.3"),
        NextHopDiscard(),
        NextHopVrf("BLUE"),
    ]
    result = normalize(values)
    assert [v["type"] for v in result] == ["ip", "interface", "discard", "vrf"]
    assert result[0]["ip"] == "192.0.2.2"
    assert result[1]["interface"] == "Ethernet0" and result[1]["ip"] == "192.0.2.3"
    assert result[3]["vrf"] == "BLUE"


def direct(state, operation, parameters):
    from app.infrastructure.sdk import SessionFactory
    from app.infrastructure.settings import Settings
    from app.modules.analysis.controller import normalize

    client, db, app, headers, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    with SessionFactory(
        db, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    ).for_job(context) as session:
        query = session.q.routes if operation == "routes" else session.q.lpmRoutes
        return normalize(query(**parameters).answer(snapshot=context.engine_snapshot).dict())[
            "answerElements"
        ][0]


def assert_sdk(state, operation, request, sdk_parameters):
    result, page = analyze(state, operation, request)
    raw = direct(state, operation, sdk_parameters)
    assert {c["key"] for c in page["columns"]} == {
        c["name"] for c in raw["metadata"]["columnMetadata"]
    }
    assert sorted(json.dumps(r, sort_keys=True) for r in page["rows"]) == sorted(
        json.dumps(r, sort_keys=True) for r in raw["rows"]
    )
    return result, page


@pytest.mark.integration
@pytest.mark.parametrize("fixture_name", ["small_network", "cisco_four"])
def test_routes_and_lpm_match_sdk(routing_app, fixture_name, monkeypatch):
    state = initialize(routing_app, fixture_name)
    client, db, app, headers, network, snapshot, actor = state
    controller = app.state.analysis_service._controller
    original = controller.run
    seen_phases = []

    def observe(context, question, params, **kwargs):
        jobs = app.state.jobs_service.list(actor, status="running").items
        seen_phases.extend(j.phase for j in jobs)
        return original(context, question, params, **kwargs)

    monkeypatch.setattr(controller, "run", observe)
    result, page = assert_sdk(state, "routes", {}, {})
    assert page["total"] > 0 and isinstance(page["rows"][0]["Next_Hop"], dict)
    assert result["effective_parameters"]["request"]["options"]["prefix_match_type"] == "EXACT"
    ip = "10.0.0.2" if fixture_name == "small_network" else "10.64.0.4"
    result, lpm = assert_sdk(state, "lpm-routes", {"ip": ip}, {"ip": ip})
    assert {c["key"] for c in lpm["columns"]} == {"Node", "VRF", "Ip", "Network", "Num_Routes"}
    assert "dataplane_or_query" in seen_phases
    _, bgp = assert_sdk(state, "routes", {"options": {"rib": "bgp"}}, {"rib": "bgp"})
    assert bgp["total"] == 0


@pytest.mark.integration
def test_route_filters_default_and_multiple_vrfs(routing_app):
    fixture = Path(__file__).parent / "fixtures/cisco_four/configs"
    files = []
    for p in fixture.iterdir():
        text = p.read_text()
        if p.name == "c1.cfg":
            text = text.replace(
                "end",
                """ip vrf BLUE
 rd 65000:100
!
interface Loopback100
 ip vrf forwarding BLUE
 ip address 10.99.0.1 255.255.255.255
!
ip route 0.0.0.0 0.0.0.0 172.20.12.2
ip route 10.64.0.4 255.255.255.255 172.20.12.2
ip route 198.51.100.0 255.255.255.0 Null0
ip route vrf BLUE 203.0.113.0 255.255.255.0 Null0
end""",
            )
        files.append((p.name, text.encode()))
    state = initialize(routing_app, files=files)
    _, page = assert_sdk(
        state, "routes", {"options": {"network": "10.64.0.4/32"}}, {"network": "10.64.0.4/32"}
    )
    assert {"static", "ospf", "connected"} <= {r["Protocol"] for r in page["rows"]}
    _, default = assert_sdk(
        state, "routes", {"options": {"network": "0.0.0.0/0"}}, {"network": "0.0.0.0/0"}
    )
    assert any(r["Network"] == "0.0.0.0/0" for r in default["rows"])
    _, blue = assert_sdk(
        state,
        "routes",
        {"options": {"vrfs": {"mode": "literal", "values": ["BLUE"]}}},
        {"vrfs": "^BLUE$"},
    )
    assert blue["rows"] and {r["VRF"] for r in blue["rows"]} == {"BLUE"}
    assert any(r["Next_Hop"]["type"] == "discard" for r in blue["rows"])
    for match in ["EXACT", "LONGEST_PREFIX_MATCH", "LONGER_PREFIXES", "SHORTER_PREFIXES"]:
        _, page = assert_sdk(
            state,
            "routes",
            {"options": {"network": "10.64.0.0/24", "prefix_match_type": match}},
            {"network": "10.64.0.0/24", "prefixMatchType": match},
        )
    assert_sdk(state, "routes", {"options": {"protocols": ["static"]}}, {"protocols": "static"})
    assert_sdk(
        state,
        "lpm-routes",
        {"ip": "203.0.113.5", "options": {"vrfs": {"mode": "literal", "values": ["BLUE"]}}},
        {"ip": "203.0.113.5", "vrfs": "^BLUE$"},
    )


@pytest.mark.integration
def test_routing_context_and_phase_fencing(routing_app):
    from app.contracts.errors import ServiceError

    state = initialize(routing_app)
    client, db, app, headers, network, snapshot, actor = state
    base = f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses"
    for operation, body in [
        ("routes", {"options": {"network": "::/0"}}),
        ("routes", {"options": {"network": "10.0.0.0"}}),
        ("routes", {"options": {"network": "10.0.0.0/255.255.255.0"}}),
        ("routes", {"options": {"network": "10.0.0.0/0.0.0.255"}}),
        ("lpm-routes", {"ip": "::1"}),
    ]:
        response = client.post(base + "/" + operation, json=body, headers=headers)
        assert response.status_code == 422 and response.json()["error"]["field_errors"]
    job = client.post(base + "/routes", json={}, headers=headers).json()
    claimed = app.state.jobs_service.claim("worker-a")
    assert str(claimed.id) == job["id"]
    with pytest.raises(ServiceError):
        app.state.jobs_service.set_phase(claimed.id, "stale-worker", "dataplane_or_query")
    assert app.state.jobs_service.get(actor, claimed.id).phase == "starting"
    app.state.jobs_service.set_phase(claimed.id, "worker-a", "dataplane_or_query")
    assert app.state.jobs_service.get(actor, claimed.id).phase == "dataplane_or_query"
    app.state.jobs_service.finish(claimed.id, "worker-a", status="failed")
    with pytest.raises(ServiceError):
        app.state.jobs_service.set_phase(claimed.id, "worker-a", "querying")
    assert app.state.jobs_service.get(actor, claimed.id).phase == "failed"
    assert_sdk(state, "routes", {"nodes": {"mode": "literal", "values": ["c1"]}}, {"nodes": "c1"})
    result, page = assert_sdk(
        state,
        "lpm-routes",
        {"ip": "203.0.113.7", "nodes": {"mode": "literal", "values": ["c2"]}},
        {"ip": "203.0.113.7", "nodes": "c2"},
    )
    assert page["total"] == 0 and "No matching rows" in result["warnings"]
