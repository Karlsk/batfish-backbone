import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from app.contracts.errors import ServiceError
from app.modules.analysis.registry import Registry
from tests import test_networks
from tests.test_filters import analyze
from tests.test_inventory import initialize

search_app = test_networks.network_app


def scoped(name):
    return {"mode": "literal", "values": [name]}


def search_request(*, action="permit"):
    return {
        "nodes": scoped("c2"),
        "filters": scoped("WEB-SEARCH"),
        "action": action,
        "options": {"headers": {"source_ip": "10.64.0.1", "destination_ip": "10.64.0.2"}},
    }


def reachability_request():
    return {"nodes": scoped("c2"), "filters": scoped("WEB-SEARCH")}


def test_search_contract_limits_scope_and_sdk_mapping():
    from unittest.mock import Mock

    from app.modules.analysis.controllers.filters import QUERIES

    registry = Registry()
    parsed = registry.validate("search-filters", search_request())
    assert parsed.action == "permit"
    assert registry.get("search-filters").requires_dataplane
    session = Mock()
    QUERIES["searchFilters"](session, parsed.model_dump(mode="json"))
    kwargs = session.q.searchFilters.call_args.kwargs
    assert set(kwargs) == {"nodes", "filters", "action", "headers"}
    assert kwargs["headers"].srcIps == "10.64.0.1"
    assert kwargs["headers"].dstIps == "10.64.0.2"
    assert kwargs["action"] == "permit"
    for invalid in (
        search_request() | {"nodes": {"mode": "expression", "expression": "/.*/"}},
        search_request() | {"filters": scoped("WEB-SEARCH") | {"expression": ".*"}},
        search_request() | {"nodes": {"mode": "literal", "values": [str(i) for i in range(11)]}},
        search_request() | {"options": {"headers": {"source_ip": "10.64.0.1"}}},
        search_request() | {"action": "matchLine 0"},
        search_request(action="match_line"),
        search_request()
        | {"options": {"headers": search_request()["options"]["headers"], "host": "elsewhere"}},
    ):
        with pytest.raises(ServiceError):
            registry.validate("search-filters", invalid)
    match_line = search_request(action="match_line")
    match_line["options"]["line_number"] = 2
    QUERIES["searchFilters"](
        session, registry.validate("search-filters", match_line).model_dump(mode="json")
    )
    assert session.q.searchFilters.call_args.kwargs["action"] == "matchLine 2"


def test_reachability_contract_uses_boolean_and_fixed_sdk_mapping():
    from unittest.mock import Mock

    from app.modules.analysis.controllers.filters import QUERIES

    registry = Registry()
    parsed = registry.validate("filter-line-reachability", reachability_request())
    assert parsed.options.ignore_composites is True
    assert not registry.get("filter-line-reachability").requires_dataplane
    session = Mock()
    QUERIES["filterLineReachability"](session, parsed.model_dump(mode="json"))
    kwargs = session.q.filterLineReachability.call_args.kwargs
    assert set(kwargs) == {"nodes", "filters", "ignoreComposites"}
    assert kwargs["nodes"].startswith("/^(?:") and kwargs["filters"].startswith("/^(?:")
    assert kwargs["ignoreComposites"] is True
    for invalid in (
        reachability_request() | {"nodes": {"mode": "expression", "expression": "/.*/"}},
        reachability_request() | {"options": {"ignore_composites": "false"}},
        reachability_request() | {"options": {"startLocation": "other"}},
    ):
        with pytest.raises(ServiceError):
            registry.validate("filter-line-reachability", invalid)


def search_acl_files():
    fixture = Path(__file__).parent / "fixtures/cisco_four/configs"
    files = []
    for path in sorted(fixture.glob("*.cfg")):
        source = path.read_text()
        if path.name == "c2.cfg":
            source = source.replace(
                "end",
                """object-group network EMPTY-GROUP
!
ip access-list extended WEB-SEARCH
 permit ip host 10.64.0.1 host 10.64.0.2
 deny ip any any
 permit ip object-group EMPTY-GROUP any
 permit ip host 10.64.0.1 host 10.64.0.4
!
end""",
            )
        files.append((path.name, source.encode()))
    return files


@pytest.fixture
def search_state(search_app):
    return initialize(search_app, files=search_acl_files())


@pytest.mark.integration
def test_search_filter_witness_can_be_retested_with_real_sdk(search_state):
    from pybatfish.datamodel import HeaderConstraints

    from app.infrastructure.sdk import SessionFactory
    from app.infrastructure.settings import Settings
    from app.modules.analysis.controller import normalize

    result, page = analyze(search_state, "search-filters", search_request())
    assert result["summary"]["returned_rows"] >= 1
    row = page["rows"][0]
    assert row["Action"] == "PERMIT"
    assert row["Flow"]["srcIp"] == "10.64.0.1"
    assert row["Flow"]["dstIp"] == "10.64.0.2"
    assert row["Line_Content"].startswith("permit")
    assert row["Source_References"]
    assert any("example flows" in warning for warning in result["warnings"])
    _, database, app, _, network, snapshot, actor = search_state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    sessions = SessionFactory(
        database, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    )
    flow = row["Flow"]
    with sessions.for_job(context) as session:
        retested = normalize(
            session.q.testFilters(
                nodes="c2",
                filters="WEB-SEARCH",
                headers=HeaderConstraints(
                    srcIps=flow["srcIp"],
                    dstIps=flow["dstIp"],
                    ipProtocols=[flow["ipProtocol"].lower()],
                    srcPorts=str(flow["srcPort"]) if flow.get("srcPort") is not None else None,
                    dstPorts=str(flow["dstPort"]) if flow.get("dstPort") is not None else None,
                ),
            )
            .answer(snapshot=context.engine_snapshot)
            .dict()
        )["answerElements"][0]["rows"]
    assert retested and retested[0]["Action"] == row["Action"]
    assert retested[0]["Line_Content"] == row["Line_Content"]


@pytest.mark.integration
def test_shadowed_and_empty_condition_preserve_distinct_sdk_reasons(search_state):
    result, page = analyze(search_state, "filter-line-reachability", reachability_request())
    assert result["kind"] == "table"
    rows = page["rows"]
    reasons = {row["Reason"] for row in rows}
    assert {"BLOCKING_LINES", "INDEPENDENTLY_UNMATCHABLE"} <= reasons
    shadowed = next(row for row in rows if row["Reason"] == "BLOCKING_LINES")
    empty = next(row for row in rows if row["Reason"] == "INDEPENDENTLY_UNMATCHABLE")
    assert shadowed["Blocking_Lines"] == ["deny ip any any"]
    assert empty["Blocking_Lines"] == []
    assert shadowed["Unreachable_Line"] != empty["Unreachable_Line"]
    assert "Sources" in shadowed and "Additional_Info" in empty


@pytest.mark.integration
def test_no_witness_is_scoped_and_not_a_safety_proof(search_state):
    request = search_request()
    request["options"]["headers"] = {"source_ip": "192.0.2.1", "destination_ip": "198.51.100.1"}
    result, page = analyze(search_state, "search-filters", request)
    assert page["total"] == 0 and page["rows"] == []
    assert any("not a network-wide safety proof" in warning for warning in result["warnings"])


@pytest.mark.integration
@pytest.mark.parametrize(
    "operation,body",
    [
        ("search-filters", search_request()),
        ("filter-line-reachability", reachability_request()),
    ],
)
def test_unsupported_vendor_acl_diagnostics_are_rejected(search_app, operation, body):
    state = initialize(search_app, "small_network")
    client, _, _, headers, network, snapshot, _ = state
    response = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/{operation}",
        json=body,
        headers=headers,
    )
    assert response.status_code == 409
    assert "ACL" in json.dumps(response.json())
