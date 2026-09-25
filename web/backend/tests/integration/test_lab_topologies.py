"""Web integration inputs; no physical-device or Java model-fidelity oracle."""

import json
import os
import subprocess
from pathlib import Path

import httpx
import pytest
from pybatfish.client.session import Session
from pybatfish.datamodel import HeaderConstraints

pytestmark = [pytest.mark.integration, pytest.mark.lab]


@pytest.fixture(scope="module")
def lab():
    manifest = os.environ.get("BATFISH_LAB_MANIFEST")
    assert manifest, "Start and seed web/scripts/lab.py; set BATFISH_LAB_MANIFEST"
    state = json.loads(Path(manifest).read_text())
    assert state["host"] == "127.0.0.1" and state["isolated"] is True
    assert set(state["snapshots"]) == {"r1-r2", "cisco-four"}
    return state


@pytest.fixture(params=["r1-r2", "cisco-four"])
def topology(request, lab):
    profile = lab["snapshots"][request.param]
    session = Session(host=lab["host"], port=lab["engine_port"], timeout=15)
    session.set_network(profile["network"])
    session.set_snapshot(profile["snapshot"])
    return session, profile


@pytest.mark.smoke
def test_real_api_and_database_smoke(lab):
    response = httpx.get(f"{lab['api_url']}/api/v1/health/live", timeout=5)
    assert response.status_code == 200 and response.json() == {"status": "alive"}
    assert response.headers["x-request-id"]
    # No readiness producer exists in MVP-02. Do not turn it green with a fake provider.
    response = httpx.get(f"{lab['api_url']}/api/v1/health/ready", timeout=5)
    assert response.status_code == 503 and response.json()["error"]["code"] == "NOT_READY"
    result = subprocess.run(
        [
            "docker",
            "exec",
            lab["database_container"],
            "psql",
            "-U",
            "batfish_test",
            "-d",
            "batfish_test",
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "SELECT version_num FROM alembic_version",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.stdout.strip() == lab["database_migration"]


@pytest.mark.smoke
def test_seeded_inventory(topology):
    session, profile = topology
    frame = session.q.nodeProperties(properties="Configuration_Format").answer().frame()
    assert set(frame.Node) == set(profile["nodes"])
    assert len(frame) == len(profile["nodes"])


def test_configuration_initialization_and_diagnostics(topology):
    session, profile = topology
    frame = session.q.fileParseStatus().answer().frame()
    assert len(frame) == len(profile["nodes"])
    assert set(frame.Status) == {"PASSED"}
    assert session.q.parseWarning().answer().frame().empty
    assert session.q.initIssues().answer().frame().empty


def test_interface_route_and_lpm_queries(topology):
    session, profile = topology
    interfaces = session.q.interfaceProperties(properties="Primary_Address").answer().frame()
    assert not interfaces.empty
    routes = (
        session.q.routes(nodes=profile["start"], network=profile["destination"] + "/32")
        .answer()
        .frame()
    )
    assert not routes.empty
    lpm = session.q.lpmRoutes(nodes=profile["start"], ip=profile["destination"]).answer().frame()
    assert not lpm.empty and profile["destination"] + "/32" in set(lpm.Network)


def test_traceroute_query_returns_structured_paths(topology):
    session, profile = topology
    answer = session.q.traceroute(
        startLocation=profile["start"],
        headers=HeaderConstraints(
            srcIps=profile["source_ip"], dstIps=profile["destination"], ipProtocols=["ICMP"]
        ),
        maxTraces=5,
    ).answer()
    json.dumps(dict(answer), allow_nan=False)
    frame = answer.frame()
    assert not frame.empty
    for row in frame.itertuples():
        assert row.TraceCount >= len(row.Traces) >= 1
        assert any(trace.disposition == "ACCEPTED" for trace in row.Traces)
        assert all(trace.hops for trace in row.Traces)


def test_two_profiles_remain_isolated_when_interleaved(lab):
    sessions = []
    for profile in lab["snapshots"].values():
        session = Session(host=lab["host"], port=lab["engine_port"], timeout=15)
        session.set_network(profile["network"])
        session.set_snapshot(profile["snapshot"])
        sessions.append((session, profile))
    for session, profile in sessions * 2:
        nodes = session.q.nodeProperties(properties="Configuration_Format").answer().frame()
        assert set(nodes.Node) == set(profile["nodes"])
