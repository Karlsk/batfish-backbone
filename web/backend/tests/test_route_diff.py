"""Known route changes establish SDK differential direction on the pinned engine."""

import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from app.infrastructure.sdk import SessionFactory
from app.infrastructure.settings import Settings
from app.modules.analysis.controller import normalize
from tests import test_networks
from tests.test_comparisons import create_comparison
from tests.test_inventory import initialize
from tests.test_snapshots import create
from tests.test_uploads import upload

pytestmark = pytest.mark.integration
route_diff_app = test_networks.network_app


def route_pair(
    route_diff_app,
    baseline_routes="ip route 198.51.100.0 255.255.255.0 Null0",
    candidate_routes="ip route 203.0.113.0 255.255.255.0 Null0",
):
    folder = Path(__file__).parent / "fixtures/cisco_four/configs"
    baseline_files, candidate_files = [], []
    for path in sorted(folder.glob("*.cfg")):
        content = path.read_bytes()
        if path.name == "c1.cfg":
            baseline = content.replace(b"end", baseline_routes.encode() + b"\nend")
            candidate = content.replace(b"end", candidate_routes.encode() + b"\nend")
        else:
            baseline = candidate = content
        baseline_files.append((path.name, baseline))
        candidate_files.append((path.name, candidate))
    state = initialize(route_diff_app, files=baseline_files)
    client, db, app, headers, network, baseline, actor = state
    source = upload(client, headers, network, files=candidate_files).json()
    submitted = create(client, headers, network, source, display_name="Candidate")
    assert submitted.status_code == 202, submitted.text
    assert app.state.execution_service.run_once("worker")
    candidate = submitted.json()["snapshot_id"]
    comparison = create_comparison(client, headers, network, baseline, candidate)
    assert comparison.status_code == 201, comparison.text
    return client, db, app, headers, comparison.json(), actor


def test_route_added_removed_direction(route_diff_app):
    client, db, app, headers, comparison, actor = route_pair(route_diff_app)
    context = app.state.changes_service.context(actor, UUID(comparison["id"]))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    with SessionFactory(
        db, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    ).for_job(context) as session:
        raw = normalize(
            session.q.routes(nodes="c1", protocols="static")
            .answer(
                snapshot=context.engine_snapshot,
                reference_snapshot=context.engine_reference_snapshot,
            )
            .dict()
        )["answerElements"][0]
    rows = raw["rows"]
    assert {row["Network"]: row["Entry_Presence"] for row in rows} == {
        "198.51.100.0/24": "Only in Reference",
        "203.0.113.0/24": "Only in Snapshot",
    }
    assert {row["Network"]: row.get("Snapshot_Next_Hop") for row in rows}["203.0.113.0/24"] == {
        "type": "discard"
    }
    submitted = client.post(
        f"/api/v1/comparisons/{comparison['id']}/analyses/routes-diff",
        json={"nodes": {"mode": "literal", "values": ["c1"]}, "options": {"protocols": ["static"]}},
        headers=headers,
    )
    assert submitted.status_code == 202, submitted.text
    assert app.state.execution_service.run_once("worker")
    job = client.get(f"/api/v1/jobs/{submitted.json()['id']}").json()
    assert job["status"] == "succeeded", job.get("error")
    result = client.get(f"/api/v1/results/{job['result_id']}").json()
    page = client.get(f"/api/v1/results/{job['result_id']}/rows").json()
    assert result["context"]["snapshot_id"] == comparison["candidate_snapshot_id"]
    assert result["context"]["reference_snapshot_id"] == comparison["baseline_snapshot_id"]
    assert {row["Network"]: row["Change"] for row in page["rows"]} == {
        "198.51.100.0/24": "removed",
        "203.0.113.0/24": "added",
    }
    assert {row["Network"]: row["Entry_Presence"] for row in page["rows"]} == {
        row["Network"]: row["Entry_Presence"] for row in rows
    }


def test_no_differences_with_prefix_filter(route_diff_app):
    client, db, app, headers, comparison, actor = route_pair(route_diff_app)
    submitted = client.post(
        f"/api/v1/comparisons/{comparison['id']}/analyses/routes-diff",
        json={"options": {"network": "10.64.0.1/32"}},
        headers=headers,
    )
    assert submitted.status_code == 202, submitted.text
    assert app.state.execution_service.run_once("worker")
    job = client.get(f"/api/v1/jobs/{submitted.json()['id']}").json()
    assert job["status"] == "succeeded", job.get("error")
    result = client.get(f"/api/v1/results/{job['result_id']}").json()
    page = client.get(f"/api/v1/results/{job['result_id']}/rows").json()
    assert page["total"] == 0 and page["rows"] == []
    assert any("selected scope" in warning for warning in result["warnings"])


def test_ecmp_route_change(route_diff_app):
    baseline_routes = "\n".join(
        [
            "ip route 192.0.2.0 255.255.255.0 172.20.12.2",
            "ip route 192.0.2.0 255.255.255.0 172.20.13.2",
        ]
    )
    candidate_routes = "\n".join(
        [
            "ip route 192.0.2.0 255.255.255.0 172.20.12.2",
            "ip route 192.0.2.0 255.255.255.0 Null0",
        ]
    )
    client, db, app, headers, comparison, actor = route_pair(
        route_diff_app, baseline_routes, candidate_routes
    )
    context = app.state.changes_service.context(actor, UUID(comparison["id"]))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    with SessionFactory(
        db, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    ).for_job(context) as session:
        raw = normalize(
            session.q.routes(nodes="c1", network="192.0.2.0/24", protocols="static")
            .answer(
                snapshot=context.engine_snapshot,
                reference_snapshot=context.engine_reference_snapshot,
            )
            .dict()
        )["answerElements"][0]
    assert [row["Entry_Presence"] for row in raw["rows"]] == [
        "Only in Reference",
        "Only in Snapshot",
        "Unchanged",
    ]
    submitted = client.post(
        f"/api/v1/comparisons/{comparison['id']}/analyses/routes-diff",
        json={
            "nodes": {"mode": "literal", "values": ["c1"]},
            "options": {"network": "192.0.2.0/24", "protocols": ["static"]},
        },
        headers=headers,
    )
    assert submitted.status_code == 202, submitted.text
    assert app.state.execution_service.run_once("worker")
    job = client.get(f"/api/v1/jobs/{submitted.json()['id']}").json()
    assert job["status"] == "succeeded", job.get("error")
    page = client.get(f"/api/v1/results/{job['result_id']}/rows").json()
    assert page["total"] == 2
    assert [row["Change"] for row in page["rows"]] == ["removed", "added"]
    assert [row["Network"] for row in page["rows"]] == ["192.0.2.0/24"] * 2
    assert page["rows"][0]["Reference_Next_Hop"]["ip"] == "172.20.13.2"
    assert page["rows"][1]["Snapshot_Next_Hop"] == {"type": "discard"}


def test_route_attribute_change_preserves_both_sides(route_diff_app):
    client, db, app, headers, comparison, actor = route_pair(
        route_diff_app,
        "ip route 192.0.2.0 255.255.255.0 Null0 1",
        "ip route 192.0.2.0 255.255.255.0 Null0 5",
    )
    context = app.state.changes_service.context(actor, UUID(comparison["id"]))
    lab = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    with SessionFactory(
        db, Settings(batfish_host=lab["host"], batfish_port=lab["engine_port"])
    ).for_job(context) as session:
        raw = normalize(
            session.q.routes(nodes="c1", network="192.0.2.0/24", protocols="static")
            .answer(
                snapshot=context.engine_snapshot,
                reference_snapshot=context.engine_reference_snapshot,
            )
            .dict()
        )["answerElements"][0]
    assert len(raw["rows"]) == 1
    assert raw["rows"][0]["Entry_Presence"] == "Changed"
    assert raw["rows"][0]["Snapshot_Admin_Distance"] == 5
    assert raw["rows"][0]["Reference_Admin_Distance"] == 1
    submitted = client.post(
        f"/api/v1/comparisons/{comparison['id']}/analyses/routes-diff",
        json={"options": {"network": "192.0.2.0/24", "protocols": ["static"]}},
        headers=headers,
    )
    assert submitted.status_code == 202, submitted.text
    assert app.state.execution_service.run_once("worker")
    job = client.get(f"/api/v1/jobs/{submitted.json()['id']}").json()
    assert job["status"] == "succeeded", job.get("error")
    page = client.get(f"/api/v1/results/{job['result_id']}/rows").json()
    assert page["total"] == 1
    assert page["rows"][0]["Change"] == "changed"
    assert page["rows"][0]["Entry_Presence"] == "Changed"
    assert page["rows"][0]["Snapshot_Admin_Distance"] == 5
    assert page["rows"][0]["Reference_Admin_Distance"] == 1


def test_route_request_cache_export_and_deleted_history(route_diff_app):
    client, db, app, headers, comparison, actor = route_pair(route_diff_app)
    endpoint = f"/api/v1/comparisons/{comparison['id']}/analyses/routes-diff"
    for body in [
        {"options": {"snapshot": "other"}},
        {"options": {"network": "2001:db8::/32"}},
        {"options": {"rib": "evpn"}},
    ]:
        assert client.post(endpoint, json=body, headers=headers).status_code == 422
    body = {"options": {"protocols": ["static"]}}
    first = client.post(endpoint, json=body, headers=headers | {"Idempotency-Key": "route-once"})
    assert first.status_code == 202, first.text
    duplicate = client.post(
        endpoint, json=body, headers=headers | {"Idempotency-Key": "route-once"}
    )
    assert duplicate.status_code == 202 and duplicate.json()["id"] == first.json()["id"]
    assert app.state.execution_service.run_once("worker")
    first_job = app.state.jobs_service.get(actor, UUID(first.json()["id"]))
    assert first_job.status == "succeeded", first_job.error
    again = client.post(endpoint, json=body, headers=headers | {"Idempotency-Key": "route-cache"})
    assert again.status_code == 202 and again.json()["id"] != first.json()["id"]
    assert app.state.execution_service.run_once("worker")
    cached = app.state.jobs_service.get(actor, UUID(again.json()["id"]))
    assert cached.status == "succeeded" and cached.result_id == first_job.result_id
    result_id = str(first_job.result_id)
    exported = client.get(f"/api/v1/results/{result_id}/export?format=json")
    assert exported.status_code == 200
    document = exported.json()
    assert document["metadata"]["context"]["snapshot_id"] == comparison["candidate_snapshot_id"]
    assert (
        document["metadata"]["context"]["reference_snapshot_id"]
        == comparison["baseline_snapshot_id"]
    )
    assert any(row["Entry_Presence"] == "Only in Snapshot" for row in document["data"]["rows"])
    csv_export = client.get(f"/api/v1/results/{result_id}/export?format=csv")
    assert csv_export.status_code == 200
    assert b"Entry_Presence" in csv_export.content and b"Change" in csv_export.content
    assert (
        client.delete(f"/api/v1/comparisons/{comparison['id']}", headers=headers).status_code == 204
    )
    assert client.get(f"/api/v1/results/{result_id}").status_code == 200
    assert client.post(endpoint, json=body, headers=headers).status_code == 404
