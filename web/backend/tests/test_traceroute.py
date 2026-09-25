import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from tests import test_networks
from tests.test_inventory import initialize

trace_app = test_networks.network_app


def test_trace_options_validation():
    from app.contracts.errors import ServiceError
    from app.modules.analysis.registry import Registry

    registry = Registry()
    assert registry.get("traceroute").enabled
    base = {"start_location": "c1", "destination_ip": "10.64.0.4"}
    for update in [
        {"destination_ip": "2001:db8::1"},
        {"destination_ip": 1},
        {"start_location": ""},
        {"options": {"source_ip": "::1"}},
        {"options": {"destination_ports": [443]}},
        {"options": {"ip_protocols": ["tcp", "icmp"], "destination_ports": [443]}},
        {"options": {"ip_protocols": ["tcp"], "source_ports": [-1]}},
        {"options": {"ip_protocols": ["udp"], "destination_ports": [65536]}},
        {"options": {"max_traces": 0}},
        {"options": {"max_traces": 21}},
        {"options": {"max_traces": True}},
        {"options": {"ignore_filters": "true"}},
        {"options": {"host": "elsewhere"}},
    ]:
        with pytest.raises(ServiceError):
            registry.validate("traceroute", base | update)


def trace(state, body):
    client, db, app, headers, network, snapshot, actor = state
    response = client.post(
        f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/traceroute",
        json=body,
        headers=headers,
    )
    assert response.status_code == 202, response.text
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(response.json()["id"]))
    assert job.status == "succeeded", job.error
    base = "/api/v1/results/" + str(job.result_id)
    result = client.get(base).json()
    flows = client.get(base + "/flows").json()["items"]
    paths = {
        flow["flow_id"]: client.get(base + "/flows/" + flow["flow_id"] + "/traces").json()
        for flow in flows
    }
    return result, flows, paths


def sdk_trace(state, **parameters):
    from app.infrastructure.sdk import SessionFactory
    from app.infrastructure.settings import Settings
    from app.modules.analysis.controller import normalize

    client, db, app, headers, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    with SessionFactory(
        db, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    ).for_job(context) as session:
        return normalize(
            session.q.traceroute(**parameters).answer(snapshot=context.engine_snapshot).dict()
        )["answerElements"][0]["rows"]


def compare(flows, paths, sdk):
    actual = [
        {
            "Flow": f["headers"],
            "TraceCount": f["trace_count"],
            "Traces": paths[f["flow_id"]]["items"],
        }
        for f in flows
    ]
    assert sorted(json.dumps(r, sort_keys=True) for r in actual) == sorted(
        json.dumps(r, sort_keys=True) for r in sdk
    )


@pytest.mark.integration
@pytest.mark.parametrize("fixture_name", ["small_network", "cisco_four"])
def test_trace_matches_sdk_and_model_warning_propagates(trace_app, fixture_name):
    from pybatfish.datamodel import HeaderConstraints

    state = initialize(trace_app, fixture_name)
    start, dst = ("r1", "10.0.0.2") if fixture_name == "small_network" else ("c1", "10.64.0.4")
    for destination in [dst, "203.0.113.254"]:
        result, flows, paths = trace(
            state, {"start_location": start, "destination_ip": destination}
        )
        direct = sdk_trace(
            state,
            startLocation=start,
            headers=HeaderConstraints(dstIps=destination, ipProtocols=["icmp"]),
            maxTraces=5,
            ignoreFilters=False,
        )
        compare(flows, paths, direct)
        dispositions = {t["disposition"] for p in paths.values() for t in p["items"]}
        assert ("ACCEPTED" if destination == dst else "NO_ROUTE") in dispositions
        assert result["summary"]["disposition_scope"] == "returned_traces"
        assert not result["summary"]["ignore_filters"]
        assert sum(result["summary"]["dispositions"].values()) == sum(
            f["returned_trace_count"] for f in flows
        )
        if fixture_name == "small_network":
            limits = result["summary"]["quality"]["model_limits"]
            assert result["coverage"] == "limited" and limits
            assert {item["description"] for item in limits} <= set(result["warnings"])
            assert any(
                item["capability"] == "ipv6" and item["status"] == "unsupported" for item in limits
            )


def ecmp_state(trace_app):
    fixture = Path(__file__).parent / "fixtures/cisco_four/configs"
    files = []
    for p in fixture.iterdir():
        config = p.read_text()
        if p.name == "c2.cfg":
            config = config.replace(
                "end",
                """ip access-list extended BLOCK-TRACE
 deny ip any host 10.64.0.4
 permit ip any any
!
interface GigabitEthernet0/0
 ip access-group BLOCK-TRACE in
!
end""",
            )
        files.append((p.name, config.encode()))
    return initialize(trace_app, files=files)


@pytest.mark.integration
def test_ecmp_mixed_dispositions_and_trace_limit(trace_app):
    from pybatfish.datamodel import HeaderConstraints

    state = ecmp_state(trace_app)
    base = {"start_location": "c1", "destination_ip": "10.64.0.4"}
    result, flows, paths = trace(state, base)
    compare(
        flows,
        paths,
        sdk_trace(
            state,
            startLocation="c1",
            headers=HeaderConstraints(dstIps="10.64.0.4", ipProtocols=["icmp"]),
            maxTraces=5,
            ignoreFilters=False,
        ),
    )
    assert {"ACCEPTED", "DENIED_IN"} <= set(result["summary"]["dispositions"])
    assert any(len(f["dispositions"]) > 1 for f in flows)
    limited, flows, paths = trace(state, base | {"options": {"max_traces": 1}})
    assert limited["truncated"] and "trace_limit" in limited["truncation_reason"]
    assert all(f["trace_count"] > f["returned_trace_count"] == 1 and f["truncated"] for f in flows)
    ignored, flows, paths = trace(
        state,
        base
        | {
            "options": {
                "ignore_filters": True,
                "source_ip": "10.64.0.1",
                "ip_protocols": ["tcp"],
                "source_ports": [12345],
                "destination_ports": [443],
            }
        },
    )
    assert (
        ignored["summary"]["ignore_filters"] and "ACL filters were ignored" in ignored["warnings"]
    )
    assert set(ignored["summary"]["dispositions"]) == {"ACCEPTED"}
    assert all(
        f["headers"]["srcIp"] == "10.64.0.1" and f["headers"]["dstPort"] == 443 for f in flows
    )


@pytest.mark.integration
def test_missing_source_is_explicit_and_recoverable(trace_app):
    state = initialize(
        trace_app,
        files=[
            ("bare.cfg", b"hostname bare\ninterface GigabitEthernet0/0\n no shutdown\n!\nend\n")
        ],
    )
    client, db, app, headers, network, snapshot, actor = state
    base = f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/traceroute"
    response = client.post(
        base, json={"start_location": "bare", "destination_ip": "192.0.2.1"}, headers=headers
    )
    assert response.status_code == 202
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(response.json()["id"]))
    assert job.status == "failed" and job.error.code == "VALIDATION_ERROR"
    assert any("source_ip" in field.path for field in job.error.field_errors)
    result, flows, paths = trace(
        state,
        {
            "start_location": "bare",
            "destination_ip": "192.0.2.1",
            "options": {"source_ip": "192.0.2.2"},
        },
    )
    assert flows and all(f["headers"]["srcIp"] == "192.0.2.2" for f in flows)


@pytest.mark.integration
def test_unknown_disposition_and_storage_truncation_summary(trace_app):
    from app.contracts.results import StructuredAnswer
    from app.infrastructure.settings import Settings
    from app.modules.results.service import ResultsService

    state = initialize(trace_app)
    client, db, app, headers, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    service = ResultsService(
        db,
        app.state.auth_service,
        Settings(data_dir=app.state.uploads_service.storage_root.parent, table_rows=1),
    )
    answer = StructuredAnswer(
        kind="traces",
        columns=(),
        rows=(
            {
                "Flow": {"ingressNode": "c1", "dstIp": "10.64.0.4"},
                "TraceCount": 2,
                "Traces": [
                    {
                        "disposition": "FUTURE_DISPOSITION",
                        "hops": [{"node": "c1", "steps": [{"action": "FUTURE_ACTION"}]}],
                    }
                ],
            },
            {
                "Flow": {"ingressNode": "c2", "dstIp": "10.64.0.4"},
                "TraceCount": 1,
                "Traces": [{"disposition": "ACCEPTED", "hops": []}],
            },
        ),
    )
    with db.transaction() as tx:
        result = service.publish(
            context,
            answer,
            parameters={
                "operation": "traceroute",
                "request": {"options": {"ignore_filters": False}},
            },
            quality={},
            cache_key=None,
            transaction=tx,
        )
    assert result.truncated and set(result.truncation_reason.split(",")) == {
        "row_limit",
        "trace_limit",
    }
    assert dict(result.summary["dispositions"]) == {"FUTURE_DISPOSITION": 1}
    assert result.summary["trace_count_scope"] == "stored_flows"
    assert result.summary["returned_trace_count"] == 1 and result.summary["trace_count"] == 2
    flow = service.flows(actor, result.id).items[0]
    path = service.traces(actor, result.id, flow.flow_id).items[0]
    assert path["hops"][0]["steps"][0]["action"] == "FUTURE_ACTION"


def test_trace_protocol_alias_mapping():
    from unittest.mock import Mock

    from app.modules.analysis.controllers.traceroute import traceroute
    from app.modules.analysis.schemas.traceroute import TraceRequest

    session = Mock()
    request = TraceRequest.model_validate(
        {
            "start_location": "c1",
            "destination_ip": "10.64.0.4",
            "options": {"ip_protocols": ["ah", "icmp"]},
        }
    )
    traceroute(session, request.model_dump(mode="json"))
    assert session.q.traceroute.call_args.kwargs["headers"].ipProtocols == ["ahp", "icmp"]
