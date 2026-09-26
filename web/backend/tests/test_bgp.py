import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from app.contracts.errors import ServiceError
from app.modules.analysis.registry import Registry
from tests import test_networks
from tests.integration.test_mvp_acceptance import sdk_json
from tests.test_inventory import analyze, initialize
from tests.test_topology import protocol_files

inventory_app = test_networks.network_app


@pytest.mark.parametrize("mode", ["status", "compatibility"])
def test_bgp_registration_and_typed_options(mode):
    registry = Registry()
    capability = {item.id: item for item in registry.capabilities()}["bgp-sessions"]
    assert capability.enabled and capability.stage == 2 and capability.result_kind == "table"
    assert registry.validate("bgp-sessions", {}).options.mode == "status"
    assert registry.validate("bgp-sessions", {"options": {"mode": mode}}).options.mode == mode
    for invalid in [
        {"options": {"mode": "live"}},
        {"options": {"nodes": "c1"}},
        {"options": {"remote_nodes": {"mode": "literal", "values": []}}},
        {"options": {"status": "ESTABLISHED"}},
        {"options": {"snapshot": "other"}},
        {"question_id": "arbitrary"},
    ]:
        with pytest.raises(ServiceError):
            registry.validate("bgp-sessions", invalid)


def test_bgp_dispatch_uses_only_fixed_questions_and_typed_selectors():
    from unittest.mock import Mock

    from app.modules.analysis.controllers.bgp import QUERIES, question_name

    session = Mock()
    parameters = (
        Registry()
        .validate(
            "bgp-sessions",
            {
                "options": {
                    "mode": "compatibility",
                    "nodes": {"mode": "literal", "values": ["c.1"]},
                    "remote_nodes": {"mode": "expression", "expression": "c2|c3"},
                }
            },
        )
        .model_dump(mode="json")
    )
    assert question_name(parameters) == "bgpSessionCompatibility"
    QUERIES[question_name(parameters)](session, parameters)
    kwargs = session.q.bgpSessionCompatibility.call_args.kwargs
    assert kwargs["nodes"].startswith("/^(?:") and "c.1" not in kwargs["nodes"]
    assert kwargs["remoteNodes"] == "c2|c3"
    assert "mode" not in kwargs and "status" not in kwargs
    assert question_name({"options": {"mode": "status"}}) == "bgpSessionStatus"


@pytest.mark.integration
@pytest.mark.parametrize("fixture_name", ["protocols", "as_mismatch", "small_network"])
def test_bgp_matches_fixed_sdk_and_preserves_model_semantics(inventory_app, fixture_name):
    from app.infrastructure.sdk import SessionFactory
    from app.infrastructure.settings import Settings

    files = protocol_files() if fixture_name != "small_network" else None
    if fixture_name == "as_mismatch":
        files = [
            (
                name,
                content.replace(
                    b"neighbor 172.20.12.2 remote-as 65000", b"neighbor 172.20.12.2 remote-as 65001"
                )
                if name == "c1.cfg"
                else content,
            )
            for name, content in files
        ]
    state = initialize(
        inventory_app,
        "small_network" if fixture_name == "small_network" else "cisco_four",
        files=files,
    )
    client, database, app, headers, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    sessions = SessionFactory(
        database, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    )
    result_ids = []
    for mode in ("status", "compatibility"):
        result, page = analyze(state, "bgp-sessions", {"options": {"mode": mode}})
        assert result["kind"] == "table"
        result_ids.append(result["id"])
        question = "bgpSessionStatus" if mode == "status" else "bgpSessionCompatibility"
        with sessions.for_job(context) as session:
            raw = sdk_json(
                getattr(session.q, question)().answer(snapshot=context.engine_snapshot).dict()
            )["answerElements"][0]
        assert {column["key"] for column in page["columns"]} == {
            column["name"] for column in raw["metadata"]["columnMetadata"]
        }
        assert sorted(json.dumps(row, sort_keys=True) for row in page["rows"]) == sorted(
            json.dumps(row, sort_keys=True) for row in raw["rows"]
        )
        assert any("model" in warning.lower() for warning in result["warnings"])
        if fixture_name == "protocols" and mode == "status":
            assert any(row["Established_Status"] == "ESTABLISHED" for row in page["rows"])
        if fixture_name == "as_mismatch" and mode == "status":
            assert any(
                row["Node"]["name"] == "c1"
                and "172.20.12.2" in json.dumps(row["Remote_IP"])
                and row["Established_Status"] == "NOT_COMPATIBLE"
                for row in page["rows"]
            )
        if fixture_name == "as_mismatch" and mode == "compatibility":
            assert any(
                row["Node"]["name"] == "c1"
                and "172.20.12.2" in json.dumps(row["Remote_IP"])
                and row["Configured_Status"] != "UNIQUE_MATCH"
                for row in page["rows"]
            )
        if fixture_name == "small_network":
            assert not page["rows"]
            assert any("IPv6" in warning for warning in result["warnings"])
    assert len(set(result_ids)) == 2
    if fixture_name == "protocols":
        selected = {
            "mode": "status",
            "nodes": {"mode": "literal", "values": ["c1"]},
            "remote_nodes": {"mode": "literal", "values": ["c2"]},
        }
        _, page = analyze(state, "bgp-sessions", {"options": selected})
        with sessions.for_job(context) as session:
            raw = sdk_json(
                session.q.bgpSessionStatus(nodes="c1", remoteNodes="c2")
                .answer(snapshot=context.engine_snapshot)
                .dict()
            )["answerElements"][0]["rows"]
        assert page["rows"] and sorted(
            json.dumps(row, sort_keys=True) for row in page["rows"]
        ) == sorted(json.dumps(row, sort_keys=True) for row in raw)
    invalid = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/bgp-sessions",
        json={"options": {"status": "ESTABLISHED"}},
        headers=headers,
    )
    assert invalid.status_code == 422


@pytest.mark.integration
def test_bgp_ipv6_vendor_input_keeps_unsupported_coverage(inventory_app):
    fixture = Path(__file__).parent / "fixtures/small_network/configs"
    files = []
    for name, peer in (("r1.cfg", "2001:db8:12::2"), ("r2.cfg", "2001:db8:12::1")):
        original = (fixture / name).read_text()
        # The uploaded source really requests an IPv6 BGP peer. The current
        # Huawei/H3C model must not turn a missing row into a healthy session.
        ipv6 = (
            "bgp 65000\n"
            f" peer {peer} as-number 65000\n"
            " ipv6-family unicast\n"
            f"  peer {peer} enable\n"
            "#\n"
        )
        files.append((name, original.replace("return", ipv6 + "return").encode()))
    state = initialize(inventory_app, "small_network", files=files)
    client, _, _, _, network, snapshot, _ = state
    result, page = analyze(state, "bgp-sessions", {})
    quality = client.get(f"/api/v1/networks/{network}/snapshots/{snapshot}").json()[
        "quality_summary"
    ]
    assert set(quality["file_formats"]) == {"HUAWEI_VRP", "H3C_COMWARE"}
    assert all(
        item["status"] != "supported"
        for item in quality["model_limits"]
        if item["capability"] == "ipv6"
    )
    assert not any(row.get("Established_Status") == "ESTABLISHED" for row in page["rows"])
    assert any("IPv6 BGP" in warning and "not modeled" in warning for warning in result["warnings"])
