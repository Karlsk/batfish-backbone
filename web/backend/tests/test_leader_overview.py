from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.composition import create_app
from app.infrastructure.settings import Settings
from app.modules.jobs.models import Job
from app.modules.results.models import Result
from app.modules.users.service import UsersService
from tests.test_auth import NEW_PASSWORD, ORIGIN, PASSWORD, login, write_headers
from tests.test_business_concerns import network
from tests.test_persistence import migrate
from tests.test_users import add_user, ready_user

pytestmark = pytest.mark.integration


@pytest.fixture
def overview_app(database):
    migrate(database)
    user = UsersService(database).bootstrap_admin("admin", PASSWORD)
    app = create_app(Settings(auth_allowed_origins=(ORIGIN,)), database=database)
    with TestClient(app, base_url=ORIGIN) as client:
        initial = login(client)
        assert (
            client.post(
                "/api/v1/auth/password",
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
                headers=write_headers(initial.json()),
            ).status_code
            == 204
        )
        headers = write_headers(login(client, password=NEW_PASSWORD).json())
        yield client, database, user, app, headers


def test_empty_overview_and_stable_paging(overview_app):
    client, database, user, app, headers = overview_app
    with TestClient(app, base_url=ORIGIN) as guest:
        assert guest.get("/api/v1/leader/overview").status_code == 401
    empty = client.get("/api/v1/leader/overview")
    assert empty.status_code == 200
    assert empty.json()["total"] == 0
    assert empty.json()["items"] == []
    assert empty.json()["recent_comparisons"] == []
    assert empty.json()["counts"] == {
        "network_states": {},
        "snapshot_states": {},
        "analysis_job_states": {},
    }

    ids = [network(database, user.user_id) for _ in range(3)]
    page = client.get("/api/v1/leader/overview", params={"offset": 1, "limit": 1})
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["total"] == 3 and len(body["items"]) == 1
    assert body["counts"]["network_states"] == {"ready": 3}
    assert body["items"][0]["network_id"] in {str(identifier) for identifier in ids}
    assert body["items"][0]["readiness"] == "pending"
    assert body["items"][0]["check_state"] == "not_checked"
    full = client.get("/api/v1/leader/overview", params={"limit": 3}).json()
    selected = full["items"][0]
    detail = client.get(f"/api/v1/leader/networks/{selected['network_id']}")
    assert detail.status_code == 200 and detail.json() == selected
    assert client.get(f"/api/v1/leader/networks/{uuid4()}").status_code == 404
    assert client.get("/api/v1/leader/overview", params={"limit": 201}).status_code == 422

    def query_count(limit):
        count = 0

        def count_statement(*_):
            nonlocal count
            count += 1

        event.listen(database.engine, "before_cursor_execute", count_statement)
        try:
            assert client.get("/api/v1/leader/overview", params={"limit": limit}).status_code == 200
        finally:
            event.remove(database.engine, "before_cursor_execute", count_statement)
        return count

    assert query_count(3) <= query_count(1) + 2
    assert add_user(client, headers, "overview-member").status_code == 201
    with TestClient(app, base_url=ORIGIN) as member:
        ready_user(member, "overview-member")
        shared = member.get("/api/v1/leader/overview", params={"offset": 1, "limit": 1})
        assert shared.status_code == 200 and shared.json() == body


def test_newest_unready_does_not_erase_ready_source_or_reuse_old_result(overview_app):
    client, database, user, _, _ = overview_app
    network_id = network(database, user.user_id)
    old_id, ready_id, tied_id, queued_id = (
        UUID(int=1001),
        UUID(int=1002),
        UUID(int=1003),
        UUID(int=1004),
    )
    now = datetime.now(UTC)
    with database.transaction() as transaction:
        for identifier, status, created_at in [
            (old_id, "ready", now - timedelta(days=2)),
            (ready_id, "ready_with_warnings", now - timedelta(days=1)),
            (tied_id, "ready_with_warnings", now - timedelta(days=1)),
            (queued_id, "queued", now),
        ]:
            transaction.execute(
                text(
                    "INSERT INTO snapshots(id,network_id,engine_name,display_name,content_hash,created_by,status,created_at) VALUES (:id,:network,:engine,:name,:hash,:user,:status,:created)"
                ),
                {
                    "id": identifier,
                    "network": network_id,
                    "engine": f"snapshot-{identifier.hex}",
                    "name": status,
                    "hash": "a" * 64,
                    "user": user.user_id,
                    "status": status,
                    "created": created_at,
                },
            )
        transaction.execute(
            text(
                "INSERT INTO business_concerns(id,network_id,name,priority,flows,version,archived,created_by,updated_by,created_at,updated_at) VALUES (:id,:network,'Payment','high','[]'::jsonb,1,false,:user,:user,:now,:now)"
            ),
            {"id": uuid4(), "network": network_id, "user": user.user_id, "now": now},
        )
        comparison_id = uuid4()
        transaction.execute(
            text(
                "INSERT INTO comparisons(id,network_id,baseline_snapshot_id,candidate_snapshot_id,display_name,baseline_content_hash,candidate_content_hash,baseline_engine_version,candidate_engine_version,baseline_sdk_version,candidate_sdk_version,engine_version,sdk_version,coverage,created_by,created_at) VALUES (:id,:network,:baseline,:candidate,'配置变更','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','test','test','test','test','test','test','limited',:user,:now)"
            ),
            {
                "id": comparison_id,
                "network": network_id,
                "baseline": old_id,
                "candidate": ready_id,
                "user": user.user_id,
                "now": now,
            },
        )
        transaction.add(
            Result(
                id=uuid4(),
                kind="table",
                schema_version="1",
                network_id=network_id,
                snapshot_id=old_id,
                context={
                    "network_id": str(network_id),
                    "snapshot_id": str(old_id),
                    "reference_snapshot_id": None,
                    "engine_network": "test",
                    "engine_snapshot": "old",
                    "engine_reference_snapshot": None,
                    "engine_version": "test",
                    "sdk_version": "test",
                    "schema_version": "1",
                },
                effective_parameters={},
                summary={},
                warnings=[],
                coverage="complete",
                truncated=False,
                storage_key=f"old-{uuid4().hex}",
                created_at=now - timedelta(days=2),
            )
        )
    card = client.get("/api/v1/leader/overview").json()["items"][0]
    recent = client.get("/api/v1/leader/overview").json()["recent_comparisons"]
    assert len(recent) == 1
    assert recent[0]["id"] == str(comparison_id)
    assert recent[0]["network_id"] == str(network_id)
    assert recent[0]["baseline_snapshot_id"] == str(old_id)
    assert recent[0]["candidate_snapshot_id"] == str(ready_id)
    assert card["latest_snapshot"]["id"] == str(queued_id)
    assert card["latest_ready_snapshot"]["id"] == str(tied_id)
    assert card["readiness"] == "warning"
    assert card["check_state"] == "not_checked"
    assert card["concern_count"] == 1
    assert card["latest_result"] is None
    assert card["latest_job"] is None
    assert client.get("/api/v1/leader/overview").json()["counts"]["snapshot_states"] == {
        "queued": 1,
        "ready": 1,
        "ready_with_warnings": 2,
    }
    analysis_context = {
        "network_id": str(network_id),
        "snapshot_id": str(tied_id),
        "reference_snapshot_id": None,
        "engine_network": "test",
        "engine_snapshot": "tied",
        "engine_reference_snapshot": None,
        "engine_version": "test",
        "sdk_version": "test",
        "schema_version": "1",
    }
    with database.transaction() as transaction:
        result_id = uuid4()
        transaction.add(
            Result(
                id=result_id,
                kind="table",
                schema_version="1",
                network_id=network_id,
                snapshot_id=tied_id,
                context=analysis_context,
                effective_parameters={},
                summary={},
                warnings=["model limit"],
                coverage="limited",
                truncated=True,
                truncation_reason="row_limit",
                storage_key=f"latest-{uuid4().hex}",
                created_at=now,
            )
        )
        transaction.flush()
        transaction.add(
            Job(
                id=uuid4(),
                kind="analysis",
                network_id=network_id,
                snapshot_id=tied_id,
                resource_ids={"network_id": str(network_id), "snapshot_id": str(tied_id)},
                requested_parameters={},
                effective_parameters={},
                context=analysis_context,
                status="succeeded",
                phase="completed",
                result_id=result_id,
                created_by=user.user_id,
                created_at=now - timedelta(minutes=1),
            )
        )
    completed = client.get("/api/v1/leader/overview").json()["items"][0]
    assert completed["check_state"] == "succeeded"
    with database.transaction() as transaction:
        transaction.add(
            Job(
                id=uuid4(),
                kind="analysis",
                network_id=network_id,
                snapshot_id=tied_id,
                resource_ids={"network_id": str(network_id), "snapshot_id": str(tied_id)},
                requested_parameters={},
                effective_parameters={},
                context=analysis_context,
                status="interrupted",
                phase="interrupted",
                created_by=user.user_id,
                created_at=now,
            )
        )
    after = client.get("/api/v1/leader/overview").json()["items"][0]
    assert after["check_state"] == "interrupted"
    assert after["latest_result"]["id"] == str(result_id)
    assert after["latest_result"]["snapshot_id"] == str(tied_id)
    assert after["latest_result"]["coverage"] == "limited"
    assert after["latest_result"]["truncated"] is True
    assert after["latest_result"]["warning_count"] == 1
    assert client.get("/api/v1/leader/overview").json()["counts"]["analysis_job_states"] == {
        "succeeded": 1,
        "interrupted": 1,
    }
