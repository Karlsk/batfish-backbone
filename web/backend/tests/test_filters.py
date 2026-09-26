import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from app.contracts.errors import ServiceError
from app.modules.analysis.registry import Registry
from tests import test_networks
from tests.test_inventory import initialize

filter_app = test_networks.network_app


def acl_files():
    fixture = Path(__file__).parent / "fixtures/cisco_four/configs"
    files = []
    for path in sorted(fixture.glob("*.cfg")):
        text = path.read_text()
        if path.name == "c2.cfg":
            text = text.replace(
                "end",
                """ip access-list extended WEB-TEST
 permit ip host 10.64.0.1 host 10.64.0.2
 deny ip host 10.64.0.1 host 10.64.0.4
!
end""",
            )
        files.append((path.name, text.encode()))
    return files


def request(destination, filter_name="WEB-TEST"):
    return {
        "nodes": {"mode": "literal", "values": ["c2"]},
        "filters": {"mode": "literal", "values": [filter_name]},
        "source_ip": "10.64.0.1",
        "destination_ip": destination,
    }


def test_filter_contract_and_fixed_sdk_mapping():
    from unittest.mock import Mock

    from app.modules.analysis.controllers.filters import QUERIES

    registry = Registry()
    capabilities = {item.id: item for item in registry.capabilities()}
    assert capabilities["test-filters"].enabled
    assert capabilities["resolve-filters"].enabled
    parsed = registry.validate("test-filters", request("10.64.0.4"))
    assert parsed.options.ip_protocols == ("icmp",)
    for invalid in (
        request("bad-ip"),
        request("10.64.0.4") | {"snapshot": "other"},
        request("10.64.0.4") | {"options": {"protocol": "arbitrary"}},
        request("10.64.0.4") | {"options": {"source_ports": [123]}},
        request("10.64.0.4") | {"filters": "WEB-TEST"},
        request("10.64.0.4") | {"nodes": {"mode": "expression", "expression": ""}},
        {"source_ip": "10.64.0.1", "destination_ip": "10.64.0.4"},
    ):
        with pytest.raises(ServiceError):
            registry.validate("test-filters", invalid)
    with pytest.raises(ServiceError):
        registry.validate("resolve-filters", {"grammarVersion": "alternate"})
    session = Mock()
    QUERIES["testFilters"](session, parsed.model_dump(mode="json"))
    kwargs = session.q.testFilters.call_args.kwargs
    assert set(kwargs) == {"nodes", "filters", "headers"}
    assert kwargs["nodes"].startswith("/^(?:") and kwargs["filters"].startswith("/^(?:")
    assert kwargs["headers"].srcIps == "10.64.0.1"
    assert kwargs["headers"].dstIps == "10.64.0.4"
    QUERIES["resolveFilterSpecifier"](
        session, registry.validate("resolve-filters", {}).model_dump(mode="json")
    )
    assert session.q.resolveFilterSpecifier.call_args.kwargs == {"filters": "/.*/"}


def analyze(state, operation, body):
    client, _, app, headers, network, snapshot, actor = state
    response = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/{operation}",
        json=body,
        headers=headers,
    )
    assert response.status_code == 202, response.text
    assert app.state.execution_service.run_once("worker")
    finished = app.state.jobs_service.get(actor, UUID(response.json()["id"]))
    assert finished.status == "succeeded", finished.error
    result = client.get("/api/v1/results/" + str(finished.result_id)).json()
    page = client.get("/api/v1/results/" + str(finished.result_id) + "/rows").json()
    return result, page


@pytest.mark.integration
def test_permit_deny_implicit_deny_and_filter_resolution_match_sdk(filter_app):
    from pybatfish.datamodel import HeaderConstraints

    from app.infrastructure.sdk import SessionFactory
    from app.infrastructure.settings import Settings
    from app.modules.analysis.controller import normalize

    state = initialize(filter_app, files=acl_files())
    _, database, app, _, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    sessions = SessionFactory(
        database, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    )
    _, resolved = analyze(state, "resolve-filters", {"nodes": request("10.64.0.2")["nodes"]})
    assert {row["Filter_Name"] for row in resolved["rows"]} == {"WEB-TEST"}
    _, selected = analyze(
        state,
        "resolve-filters",
        {"nodes": request("10.64.0.2")["nodes"], "filter_expression": "WEB-TEST"},
    )
    assert selected["rows"] == resolved["rows"]
    with sessions.for_job(context) as session:
        raw_resolved = normalize(
            session.q.resolveFilterSpecifier(nodes="c2", filters="/.*/")
            .answer(snapshot=context.engine_snapshot)
            .dict()
        )["answerElements"][0]
    assert resolved["rows"] == raw_resolved["rows"]
    for destination, action, implicit in (
        ("10.64.0.2", "PERMIT", False),
        ("10.64.0.4", "DENY", False),
        ("10.64.0.3", "DENY", True),
    ):
        result, page = analyze(state, "test-filters", request(destination))
        assert result["kind"] == "table" and result["summary"]["returned_rows"] == 1
        assert any("not end-to-end" in warning for warning in result["warnings"])
        row = page["rows"][0]
        assert row["Action"] == action and row["Implicit_Deny"] is implicit
        with sessions.for_job(context) as session:
            raw = normalize(
                session.q.testFilters(
                    nodes="c2",
                    filters="WEB-TEST",
                    headers=HeaderConstraints(
                        srcIps="10.64.0.1", dstIps=destination, ipProtocols=["icmp"]
                    ),
                )
                .answer(snapshot=context.engine_snapshot)
                .dict()
            )["answerElements"][0]
        assert {key: row[key] for key in raw["rows"][0]} == raw["rows"][0]
        if implicit:
            assert row["Line_Content"] == "no-match" and row["Source_References"] == []
        else:
            assert row["Line_Content"].startswith(action.lower())
            assert row["Source_References"][0]["filename"] == "configs/c2.cfg"
            assert "line" not in row["Source_References"][0]
    _, tcp = analyze(
        state,
        "test-filters",
        request("10.64.0.2")
        | {
            "options": {
                "ip_protocols": ["tcp"],
                "source_ports": [12345],
                "destination_ports": [443],
            }
        },
    )
    assert tcp["rows"][0]["Action"] == "PERMIT"
    assert tcp["rows"][0]["Flow"]["ipProtocol"] == "TCP"
    assert tcp["rows"][0]["Flow"]["srcPort"] == 12345
    assert tcp["rows"][0]["Flow"]["dstPort"] == 443


@pytest.mark.integration
def test_no_such_filter_is_not_interpreted_as_permit(filter_app):
    state = initialize(filter_app, files=acl_files())
    result, page = analyze(state, "test-filters", request("10.64.0.2", "MISSING-ACL"))
    assert page["total"] == 0 and not page["rows"]
    assert any("no allow/deny" in warning for warning in result["warnings"])


@pytest.mark.integration
def test_vendor_acl_coverage_rejects_unsupported_verification(filter_app):
    state = initialize(filter_app, "small_network")
    client, _, _, headers, network, snapshot, _ = state
    response = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/test-filters",
        json=request("10.0.0.2"),
        headers=headers,
    )
    assert response.status_code == 409
    assert "ACL" in json.dumps(response.json())
