"""Fixed leader briefings preserve facts while evidence and editorial text change."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests import test_networks
from tests.test_auth import ORIGIN
from tests.test_business_concerns import body as concern_body
from tests.test_comparisons import two_snapshots
from tests.test_inventory import analyze, initialize
from tests.test_users import add_user, ready_user

pytestmark = pytest.mark.integration
briefing_app = test_networks.network_app


def _source(briefing_app):
    state = initialize(briefing_app, "small_network")
    result, _ = analyze(state, "nodes", {"options": {"properties": ["Hostname"]}})
    return state, result


def test_briefing_freezes_result_and_editorial_versions(briefing_app):
    state, result = _source(briefing_app)
    client, database, app, headers, network, snapshot, _ = state
    body = {
        "title": "周例会网络检查",
        "network_id": network,
        "snapshot_id": snapshot,
        "result_ids": [result["id"]],
        "notes": "人工备注：请复核",
    }
    key = uuid4().hex
    created = client.post(
        "/api/v1/leader/briefings", json=body, headers=headers | {"Idempotency-Key": key}
    )
    assert created.status_code == 201, created.text
    first = created.json()
    assert first["version"] == 1
    assert first["sections"][0]["summary"] == result["summary"]
    assert first["sections"][0]["evidence_available"] is True
    assert first["notes"] == body["notes"]
    again = client.post(
        "/api/v1/leader/briefings", json=body, headers=headers | {"Idempotency-Key": key}
    )
    assert again.status_code == 201 and again.json()["id"] == first["id"]
    conflict = client.post(
        "/api/v1/leader/briefings",
        json=body | {"title": "另一标题"},
        headers=headers | {"Idempotency-Key": key},
    )
    assert conflict.status_code == 409

    revised = client.patch(
        f"/api/v1/leader/briefings/{first['id']}",
        json={
            "expected_version": 1,
            "title": "周例会网络检查（修订）",
            "notes": "人工备注：已复核",
        },
        headers=headers | {"Idempotency-Key": uuid4().hex},
    )
    assert revised.status_code == 200, revised.text
    second = revised.json()
    assert second["id"] != first["id"] and second["version"] == 2
    assert second["report_id"] == first["report_id"]
    assert second["sections"] == first["sections"]
    assert client.get(f"/api/v1/leader/briefings/{first['id']}").json() == first
    assert client.get("/api/v1/leader/briefings").json()["items"][0]["id"] == second["id"]
    tampered = client.patch(
        f"/api/v1/leader/briefings/{second['id']}",
        json={"expected_version": 2, "title": "伪造结论", "sections": []},
        headers=headers | {"Idempotency-Key": uuid4().hex},
    )
    assert tampered.status_code == 422
    stale = client.patch(
        f"/api/v1/leader/briefings/{first['id']}",
        json={"expected_version": 1, "title": "旧版本覆盖"},
        headers=headers | {"Idempotency-Key": uuid4().hex},
    )
    assert stale.status_code == 409

    assert add_user(client, headers, "briefing-member").status_code == 201
    with TestClient(app, base_url=ORIGIN) as member:
        member_headers = ready_user(member, "briefing-member")
        assert member.get(f"/api/v1/leader/briefings/{first['id']}").json() == first
        member_created = member.post(
            "/api/v1/leader/briefings",
            json=body | {"title": "成员汇报"},
            headers=member_headers | {"Idempotency-Key": uuid4().hex},
        )
        assert member_created.status_code == 201
        assert (
            member.post(
                f"/api/v1/leader/briefings/{first['id']}/archive", headers=member_headers
            ).status_code
            == 403
        )
    archived = client.post(f"/api/v1/leader/briefings/{second['id']}/archive", headers=headers)
    assert archived.status_code == 200 and archived.json()["archived"] is True
    assert client.get(f"/api/v1/leader/briefings/{first['id']}").status_code == 200
    with database.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM briefing_revisions")).scalar_one() == 3


def test_briefing_rejects_foreign_sources_and_retains_deleted_evidence(briefing_app):
    state, result = _source(briefing_app)
    client, database, app, headers, network, snapshot, _ = state
    body = {
        "title": "固定事实",
        "network_id": network,
        "snapshot_id": snapshot,
        "result_ids": [result["id"]],
    }
    wrong = client.post(
        "/api/v1/leader/briefings",
        json=body | {"snapshot_id": str(uuid4())},
        headers=headers | {"Idempotency-Key": uuid4().hex},
    )
    assert wrong.status_code in {404, 409}
    duplicate = client.post(
        "/api/v1/leader/briefings",
        json=body | {"result_ids": [result["id"], result["id"]]},
        headers=headers | {"Idempotency-Key": uuid4().hex},
    )
    assert duplicate.status_code == 422
    missing = client.post(
        "/api/v1/leader/briefings",
        json=body | {"result_ids": [str(uuid4())]},
        headers=headers | {"Idempotency-Key": uuid4().hex},
    )
    assert missing.status_code == 404

    created = client.post(
        "/api/v1/leader/briefings", json=body, headers=headers | {"Idempotency-Key": uuid4().hex}
    )
    assert created.status_code == 201, created.text
    report = created.json()
    with database.transaction() as tx:
        storage_key = tx.execute(
            text("SELECT storage_key FROM results WHERE id=:id"), {"id": UUID(result["id"])}
        ).scalar_one()
    (Path(app.state.results_service._root) / storage_key).unlink()
    missing_file = client.get(f"/api/v1/leader/briefings/{report['id']}")
    assert missing_file.status_code == 200
    assert missing_file.json()["sections"][0]["evidence_available"] is False
    with database.transaction() as tx:
        tx.execute(
            text("UPDATE jobs SET result_id=NULL WHERE result_id=:id"), {"id": UUID(result["id"])}
        )
        tx.execute(text("DELETE FROM results WHERE id=:id"), {"id": UUID(result["id"])})
    after = client.get(f"/api/v1/leader/briefings/{report['id']}")
    assert after.status_code == 200
    assert after.json()["sections"][0]["summary"] == result["summary"]
    assert after.json()["sections"][0]["evidence_available"] is False


def test_briefing_freezes_warnings_and_concern_mapping_version(briefing_app):
    state, result = _source(briefing_app)
    client, database, _, headers, network, snapshot, _ = state
    with database.transaction() as tx:
        tx.execute(
            text(
                "UPDATE results SET warnings='[\"MODEL_LIMIT\"]'::jsonb, "
                "coverage='limited', truncated=true, truncation_reason='row_limit' "
                "WHERE id=:id"
            ),
            {"id": UUID(result["id"])},
        )
    concern = client.post("/api/v1/business-concerns", json=concern_body(network), headers=headers)
    assert concern.status_code == 201, concern.text
    mapped = concern.json()
    base = {
        "title": "映射冻结",
        "network_id": network,
        "snapshot_id": snapshot,
        "result_ids": [result["id"]],
        "concern_id": mapped["id"],
        "concern_version": 1,
    }
    first_response = client.post(
        "/api/v1/leader/briefings", json=base, headers=headers | {"Idempotency-Key": uuid4().hex}
    )
    assert first_response.status_code == 201, first_response.text
    first = first_response.json()
    assert first["frozen_concern"]["version"] == 1
    assert "MODEL_LIMIT" in first["warnings"]
    assert first["sections"][0]["truncated"] is True
    assert "row_limit" in first["warnings"][-1] or any(
        "row_limit" in warning for warning in first["warnings"]
    )
    changed = client.patch(
        f"/api/v1/business-concerns/{mapped['id']}",
        json={"expected_version": 1, "name": "修改后的映射"},
        headers=headers,
    )
    assert changed.status_code == 200
    with database.transaction() as tx:
        tx.execute(
            text("UPDATE results SET warnings='[]'::jsonb, coverage='complete' WHERE id=:id"),
            {"id": UUID(result["id"])},
        )
    assert client.get(f"/api/v1/leader/briefings/{first['id']}").json() == first
    second = client.post(
        "/api/v1/leader/briefings",
        json=base | {"concern_version": 2},
        headers=headers | {"Idempotency-Key": uuid4().hex},
    )
    assert second.status_code == 201
    assert second.json()["frozen_concern"]["name"] == "修改后的映射"
    assert "MODEL_LIMIT" not in second.json()["warnings"]


def test_concurrent_same_key_creates_one_briefing(briefing_app):
    state, result = _source(briefing_app)
    _, database, app, _, network, snapshot, actor = state
    from app.modules.leader.briefings_schemas import CreateBriefingRequest

    request = CreateBriefingRequest(
        title="并发固定汇报",
        network_id=UUID(network),
        snapshot_id=UUID(snapshot),
        result_ids=(UUID(result["id"]),),
    )
    service = app.state.leader_briefings_service
    key = uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(
            pool.map(
                lambda _: service.create(actor, request, idempotency_key=key, request_id=uuid4()),
                range(2),
            )
        )
    assert first.id == second.id
    with database.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM briefings")).scalar_one() == 1
        assert tx.execute(text("SELECT count(*) FROM briefing_revisions")).scalar_one() == 1


def test_briefing_rejects_existing_result_from_other_snapshot_or_network(briefing_app):
    client, _, app, headers, network, baseline, candidate, actor = two_snapshots(briefing_app)
    result, _ = analyze(
        (client, None, app, headers, network, baseline, actor),
        "nodes",
        {"options": {"properties": ["Hostname"]}},
    )
    body = {
        "title": "错源检查",
        "network_id": network,
        "snapshot_id": candidate,
        "result_ids": [result["id"]],
    }
    mismatch = client.post(
        "/api/v1/leader/briefings", json=body, headers=headers | {"Idempotency-Key": uuid4().hex}
    )
    assert mismatch.status_code == 409
    other = test_networks.create_network(client, headers, "Another network").json()["id"]
    cross_network = client.post(
        "/api/v1/leader/briefings",
        json=body | {"network_id": other},
        headers=headers | {"Idempotency-Key": uuid4().hex},
    )
    assert cross_network.status_code == 404
