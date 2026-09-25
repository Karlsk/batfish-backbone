from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.composition import create_app
from app.contracts.errors import ServiceError
from app.infrastructure.settings import Settings
from app.modules.users.service import UsersService
from tests.test_persistence import migrate

pytestmark = pytest.mark.integration
ORIGIN = "https://testserver"
PASSWORD = "initial password phrase"
NEW_PASSWORD = "changed password phrase"


@pytest.fixture
def auth_app(database):
    migrate(database)
    users = UsersService(database)
    user = users.bootstrap_admin("admin", PASSWORD)
    settings = Settings(auth_allowed_origins=(ORIGIN,), auth_failure_limit=5)
    app = create_app(settings, database=database)
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, database, user, app


def login(client, username="admin", password=PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": ORIGIN},
    )


def write_headers(body):
    return {"Origin": ORIGIN, "X-CSRF-Token": body["csrf_token"]}


def test_login_cookie_and_csrf(auth_app):
    client, database, _, _ = auth_app
    for origin in [None, "https://evil.example", "null"]:
        headers = {"Origin": origin} if origin else {}
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}, headers=headers
        )
        assert response.status_code == 403
    response = login(client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert (
        "httponly" in cookie
        and "secure" in cookie
        and "samesite=lax" in cookie
        and "path=/" in cookie
    )
    assert "max-age=28800" in cookie
    token = client.cookies["batfish_session"]
    with database.transaction() as transaction:
        stored = transaction.execute(
            text("SELECT token_hash, expires_at, created_at FROM auth_sessions")
        ).one()
        assert token != stored.token_hash and len(stored.token_hash) == 64
        assert (
            timedelta(hours=7, minutes=59)
            < stored.expires_at - stored.created_at
            < timedelta(hours=8, minutes=1)
        )
        assert (
            transaction.execute(text("SELECT password_hash FROM users"))
            .scalar_one()
            .startswith("$argon2id$")
        )
    for headers in [
        {},
        {"Origin": ORIGIN},
        {"Origin": ORIGIN, "X-CSRF-Token": "wrong"},
        {"Origin": "https://evil.example", "X-CSRF-Token": response.json()["csrf_token"]},
    ]:
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 403
    assert client.get("/api/v1/auth/me").status_code == 200
    assert (
        client.post("/api/v1/auth/logout", headers=write_headers(response.json())).status_code
        == 204
    )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_and_password_revoke(auth_app):
    client, _, _, app = auth_app
    first = login(client)
    with TestClient(app, base_url=ORIGIN) as second:
        login(second)
        result = client.post(
            "/api/v1/auth/password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers=write_headers(first.json()),
        )
        assert result.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401
        assert second.get("/api/v1/auth/me").status_code == 401
    assert login(client).status_code == 401
    assert login(client, password=NEW_PASSWORD).json()["must_change_password"] is False


def test_initial_password_restriction(auth_app):
    client, _, _, app = auth_app
    result = login(client)
    assert result.json()["must_change_password"] is True
    token = client.cookies["batfish_session"]
    with pytest.raises(ServiceError) as failure:
        app.state.auth_service.require_actor(token)
    assert failure.value.code == "FORBIDDEN"
    assert client.get("/api/v1/auth/me").status_code == 200
    response = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": PASSWORD},
        headers=write_headers(result.json()),
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=write_headers(result.json()),
    )
    assert response.status_code == 204
    login(client, password=NEW_PASSWORD)
    assert app.state.auth_service.require_actor(client.cookies["batfish_session"]).role == "admin"


def test_no_user_enumeration(auth_app):
    client, _, _, _ = auth_app
    known = login(client, password="wrong password").json()["error"]
    unknown = login(client, username="unknown", password="wrong password").json()["error"]
    known.pop("request_id")
    unknown.pop("request_id")
    assert known == unknown and known["code"] == "UNAUTHORIZED"


def test_failure_limit_shared_and_expiration(auth_app):
    client, database, _, _ = auth_app
    for _ in range(5):
        assert login(client, password="wrong password").status_code == 401
    other_app = create_app(Settings(auth_allowed_origins=(ORIGIN,)), database=database)
    with TestClient(other_app, base_url=ORIGIN) as other:
        assert login(other).status_code == 429
    with database.transaction() as transaction:
        transaction.execute(
            text("UPDATE login_attempts SET window_start=now()-interval '61 seconds'")
        )
    assert login(client).status_code == 200
    with database.transaction() as transaction:
        transaction.execute(
            text("UPDATE auth_sessions SET expires_at=:past"),
            {"past": datetime.now(UTC) - timedelta(seconds=1)},
        )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_bootstrap_once_and_redaction(auth_app):
    client, database, user, _ = auth_app
    with pytest.raises(ServiceError):
        UsersService(database).bootstrap_admin("second", PASSWORD)
    with database.transaction() as transaction:
        assert transaction.execute(text("SELECT count(*) FROM users")).scalar_one() == 1
        audit = transaction.execute(
            text("SELECT actor_id, action, outcome FROM audit_events")
        ).one()
        assert (
            audit.actor_id == user.user_id
            and audit.action == "admin.bootstrap"
            and audit.outcome == "succeeded"
        )
    result = login(client)
    serialized = result.text
    assert (
        PASSWORD not in serialized
        and "password_hash" not in serialized
        and "session_version" not in serialized
    )


def test_disabled_and_generation_revoked_sessions(auth_app):
    client, database, _, _ = auth_app
    assert login(client).status_code == 200
    with database.transaction() as transaction:
        transaction.execute(text("UPDATE users SET session_version=session_version+1"))
    assert client.get("/api/v1/auth/me").status_code == 401
    assert login(client).status_code == 200
    with database.transaction() as transaction:
        transaction.execute(text("UPDATE users SET enabled=false"))
    assert client.get("/api/v1/auth/me").status_code == 401
    assert login(client).status_code == 401


def test_concurrent_bootstrap_creates_one_admin(database):
    from concurrent.futures import ThreadPoolExecutor

    migrate(database)

    def bootstrap(username):
        try:
            return UsersService(database).bootstrap_admin(username, PASSWORD)
        except ServiceError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(bootstrap, ["first", "second"]))
    assert sum(item == "CONFLICT" for item in results) == 1
    with database.transaction() as transaction:
        assert transaction.execute(text("SELECT count(*) FROM users")).scalar_one() == 1


def test_concurrent_failures_cannot_bypass_limit(auth_app):
    from concurrent.futures import ThreadPoolExecutor

    _, _, _, app = auth_app

    def failure(_index):
        with TestClient(app, base_url=ORIGIN) as client:
            return login(client, password="wrong").status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(failure, range(6)))
    assert sorted(statuses) == [401] * 5 + [429]


def test_cookie_from_logged_out_session_is_rejected(auth_app):
    client, _, _, _ = auth_app
    response = login(client)
    token = client.cookies["batfish_session"]
    assert (
        client.post("/api/v1/auth/logout", headers=write_headers(response.json())).status_code
        == 204
    )
    client.cookies.set("batfish_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_failure_limit_scoped_to_account_and_address_pair(auth_app):
    client, _, _, app = auth_app
    for _ in range(5):
        assert login(client, password="wrong").status_code == 401
    assert login(client).status_code == 429
    assert login(client, username="someone-else", password="wrong").status_code == 401
    info, _token = app.state.auth_service.login(
        "admin", PASSWORD, origin=ORIGIN, client_address="different-client"
    )
    assert info.username == "admin"
