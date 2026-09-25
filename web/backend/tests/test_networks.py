import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.composition import create_app
from app.infrastructure.engine import EngineGate
from app.infrastructure.settings import Settings
from app.modules.users.service import UsersService
from tests.test_auth import NEW_PASSWORD, ORIGIN, PASSWORD, login, write_headers
from tests.test_persistence import migrate
from tests.test_users import add_user, ready_user

pytestmark = pytest.mark.integration


@pytest.fixture
def network_app(database, tmp_path):
    migrate(database)
    manifest = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    UsersService(database).bootstrap_admin("admin", PASSWORD)
    settings = Settings(
        data_dir=tmp_path / "data",
        auth_allowed_origins=(ORIGIN,),
        batfish_host=manifest["host"],
        batfish_port=manifest["engine_port"],
        sdk_request_timeout=10,
    )
    app = create_app(settings, database=database)
    with TestClient(app, base_url=ORIGIN) as client:
        first = login(client)
        assert (
            client.post(
                "/api/v1/auth/password",
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
                headers=write_headers(first.json()),
            ).status_code
            == 204
        )
        headers = write_headers(login(client, password=NEW_PASSWORD).json())
        yield client, database, app, headers


def create_network(client, headers, label="Lab", key=None):
    return client.post(
        "/api/v1/networks",
        json={"display_name": label},
        headers=headers | ({"Idempotency-Key": key} if key else {}),
    )


def test_team_shares_network(network_app):
    admin, _, app, headers = network_app
    created = create_network(admin, headers)
    assert created.status_code == 201 and created.json()["sync_state"] == "ready"
    add_user(admin, headers, "member")
    with TestClient(app, base_url=ORIGIN) as member:
        member_headers = ready_user(member, "member")
        assert member.get("/api/v1/networks/" + created.json()["id"]).json() == created.json()
        assert member.get("/api/v1/networks").json()["items"] == [created.json()]
        assert create_network(member, member_headers, "Member network").status_code == 201
    assert admin.get("/api/v1/networks").json()["total"] == 2


def test_same_label_different_identity(network_app):
    client, _, _, headers = network_app
    a = create_network(client, headers, "Same label").json()
    b = create_network(client, headers, "Same label").json()
    assert a["id"] != b["id"] and a["engine_name"] != b["engine_name"]
    assert client.get("/api/v1/networks").json()["total"] == 2
    assert client.get("/api/v1/networks/" + str(uuid4())).status_code == 404


def test_network_idempotency_conflict_and_scope(network_app):
    client, _, app, headers = network_app
    key = uuid4().hex
    first = create_network(client, headers, key=key)
    assert first.status_code == 201
    assert create_network(client, headers, key=key).json() == first.json()
    assert create_network(client, headers, label="Different", key=key).status_code == 409
    add_user(client, headers, "other")
    with TestClient(app, base_url=ORIGIN) as other:
        other_headers = ready_user(other, "other")
        created = create_network(other, other_headers, key=key)
        assert created.status_code == 201 and created.json()["id"] != first.json()["id"]


def test_engine_busy_preserves_pending_identity(network_app):
    client, database, _, headers = network_app
    key = uuid4().hex
    with EngineGate(database).exclusive(owner="test-holder"):
        assert create_network(client, headers, key=key).status_code == 503
        pending = client.get("/api/v1/networks").json()["items"][0]
        assert pending["sync_state"] == "pending" and pending["sync_error"] == "ENGINE_BUSY"
    recovered = create_network(client, headers, key=key)
    assert recovered.status_code == 201
    assert (
        recovered.json()["id"] == pending["id"]
        and recovered.json()["engine_name"] == pending["engine_name"]
    )
    assert recovered.json()["sync_state"] == "ready" and recovered.json()["sync_error"] is None


def test_create_writeback_failure(network_app, monkeypatch):
    from app.modules.networks.repository import NetworksRepository

    client, _, _, headers = network_app
    original = NetworksRepository.mark_ready
    attempts = 0

    def fail_once(self, network_id):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("private database writeback failure")
        return original(self, network_id)

    monkeypatch.setattr(NetworksRepository, "mark_ready", fail_once)
    key = uuid4().hex
    response = create_network(client, headers, key=key)
    assert response.status_code == 503 and "private" not in response.text
    pending = client.get("/api/v1/networks").json()["items"][0]
    assert pending["sync_state"] == "pending" and pending["sync_error"] == "WRITEBACK_FAILED"
    recovered = create_network(client, headers, key=key)
    assert recovered.status_code == 201 and recovered.json()["id"] == pending["id"]
    assert recovered.json()["engine_name"] == pending["engine_name"]
    assert client.get("/api/v1/networks").json()["total"] == 1


def test_unknown_slot_cannot_be_reused(network_app):
    client, database, _, headers = network_app
    with pytest.raises(RuntimeError):
        with EngineGate(database).exclusive(owner="failed-holder"):
            raise RuntimeError("remote result unknown")
    response = create_network(client, headers, key=uuid4().hex)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ENGINE_STATE_UNKNOWN"
    assert response.json()["error"]["retryable"] is False
    with database.transaction() as transaction:
        assert transaction.execute(text("SELECT state FROM engine_slot")).scalar_one() == "unknown"


def test_network_validation_rejects_context_overrides(network_app):
    client, _, _, headers = network_app
    for body in [
        {"display_name": ""},
        {"display_name": "x", "engine_name": "external"},
        {"display_name": "x", "actor_id": str(uuid4())},
    ]:
        assert client.post("/api/v1/networks", json=body, headers=headers).status_code == 422
    assert client.get("/api/v1/networks").json()["total"] == 0


def test_engine_lock_released_if_initial_commit_fails(network_app):
    from sqlalchemy import create_engine, event

    from app.infrastructure.engine import ENGINE_LOCK_ID

    _, database, _, _ = network_app
    failed = False

    def fail_once(_connection):
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("commit hook failure")

    event.listen(database.engine, "commit", fail_once)
    try:
        with pytest.raises(RuntimeError):
            with EngineGate(database).exclusive(owner="commit-failure"):
                pytest.fail("Must fail before SDK work")
    finally:
        event.remove(database.engine, "commit", fail_once)
    observer = create_engine(database.engine.url)
    try:
        with observer.connect() as connection:
            acquired = connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": ENGINE_LOCK_ID}
            )
            try:
                assert acquired, "Failed lock setup must not leak a session lock into the pool"
            finally:
                if acquired:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": ENGINE_LOCK_ID}
                    )
    finally:
        observer.dispose()


def test_generated_idempotency_key_can_resume_busy_request(network_app):
    client, database, _, headers = network_app
    with EngineGate(database).exclusive(owner="temporary-holder"):
        response = create_network(client, headers)
        assert response.status_code == 503
        key = response.headers["idempotency-key"]
        pending = client.get("/api/v1/networks").json()["items"][0]
    recovered = create_network(client, headers, key=key)
    assert recovered.status_code == 201 and recovered.json()["id"] == pending["id"]


def test_first_sdk_timeout_reports_unknown(network_app, monkeypatch):
    from pybatfish.client.session import Session

    client, database, _, headers = network_app

    def timeout(*args, **kwargs):
        raise TimeoutError("private remote endpoint")

    monkeypatch.setattr(Session, "set_network", timeout)
    response = create_network(client, headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ENGINE_STATE_UNKNOWN"
    assert response.json()["error"]["retryable"] is False
    assert "private" not in response.text
    with database.transaction() as transaction:
        assert transaction.execute(text("SELECT state FROM engine_slot")).scalar_one() == "unknown"
