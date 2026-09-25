import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.test_auth import (  # noqa: F401
    NEW_PASSWORD,
    ORIGIN,
    PASSWORD,
    auth_app,
    login,
    write_headers,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def admin_app(request):
    client, database, user, app = request.getfixturevalue("auth_app")
    initial = login(client)
    assert (
        client.post(
            "/api/v1/auth/password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers=write_headers(initial.json()),
        ).status_code
        == 204
    )
    credentials = login(client, password=NEW_PASSWORD).json()
    return client, database, user, app, write_headers(credentials)


def add_user(client, headers, username="member", role="member"):
    return client.post(
        "/api/v1/users",
        json={"username": username, "temporary_password": PASSWORD, "role": role},
        headers=headers,
    )


def ready_user(client, username):
    response = login(client, username=username)
    assert response.status_code == 200
    assert (
        client.post(
            "/api/v1/auth/password",
            json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            headers=write_headers(response.json()),
        ).status_code
        == 204
    )
    return write_headers(login(client, username=username, password=NEW_PASSWORD).json())


def test_member_cannot_administer(admin_app):
    admin, _, _, app, headers = admin_app
    member = add_user(admin, headers).json()
    with TestClient(app, base_url=ORIGIN) as client:
        member_headers = ready_user(client, "member")
        assert client.get("/api/v1/users").status_code == 403
        assert add_user(client, member_headers, "forbidden").status_code == 403
        assert (
            client.patch(
                "/api/v1/users/" + member["id"], json={"role": "admin"}, headers=member_headers
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/users/" + member["id"] + "/reset-password",
                json={"temporary_password": PASSWORD},
                headers=member_headers,
            ).status_code
            == 403
        )


def test_creation_pagination_and_validation(admin_app):
    client, _, _, _, headers = admin_app
    created = add_user(client, headers)
    assert created.status_code == 201
    assert created.json()["must_change_password"] is True
    assert add_user(client, headers).status_code == 409
    page = client.get("/api/v1/users", params={"limit": 1, "offset": 1})
    assert page.status_code == 200
    assert page.json()["total"] == 2 and len(page.json()["items"]) == 1
    assert page.json()["items"][0]["id"] == created.json()["id"]
    for params in [{"limit": 201}, {"offset": -1}]:
        assert client.get("/api/v1/users", params=params).status_code == 422
    for body in [
        {},
        {"password": "do not allow"},
        {"enabled": None},
        {"role": "root"},
        {"actor_id": str(UUID(int=1))},
    ]:
        assert (
            client.patch(
                "/api/v1/users/" + created.json()["id"], json=body, headers=headers
            ).status_code
            == 422
        )
    assert "password_hash" not in page.text and "session_version" not in page.text


def test_disable_revokes_sessions(admin_app):
    admin, _, _, app, headers = admin_app
    member = add_user(admin, headers).json()
    with TestClient(app, base_url=ORIGIN) as first, TestClient(app, base_url=ORIGIN) as second:
        ready_user(first, "member")
        assert login(second, username="member", password=NEW_PASSWORD).status_code == 200
        assert (
            admin.patch(
                "/api/v1/users/" + member["id"], json={"enabled": False}, headers=headers
            ).status_code
            == 200
        )
        assert first.get("/api/v1/auth/me").status_code == 401
        assert second.get("/api/v1/auth/me").status_code == 401
        assert (
            admin.patch(
                "/api/v1/users/" + member["id"], json={"enabled": True}, headers=headers
            ).status_code
            == 200
        )
        assert first.get("/api/v1/auth/me").status_code == 401
        assert second.get("/api/v1/auth/me").status_code == 401
        assert login(first, username="member", password=NEW_PASSWORD).status_code == 200


def test_password_reset_and_role_immediate(admin_app):
    admin, _, _, app, headers = admin_app
    member = add_user(admin, headers).json()
    with TestClient(app, base_url=ORIGIN) as client:
        ready_user(client, "member")
        assert (
            admin.patch(
                "/api/v1/users/" + member["id"], json={"role": "admin"}, headers=headers
            ).status_code
            == 200
        )
        assert client.get("/api/v1/users").status_code == 200
        assert (
            admin.patch(
                "/api/v1/users/" + member["id"], json={"role": "member"}, headers=headers
            ).status_code
            == 200
        )
        assert client.get("/api/v1/users").status_code == 403
        assert (
            admin.post(
                "/api/v1/users/" + member["id"] + "/reset-password",
                json={"temporary_password": PASSWORD},
                headers=headers,
            ).status_code
            == 204
        )
        assert client.get("/api/v1/auth/me").status_code == 401
        assert login(client, username="member", password=NEW_PASSWORD).status_code == 401
        response = login(client, username="member")
        assert response.status_code == 200 and response.json()["must_change_password"] is True
        assert client.get("/api/v1/users").status_code == 403


@pytest.mark.parametrize("change", [{"enabled": False}, {"role": "member"}])
def test_last_admin_guard(admin_app, change):
    first, database, first_user, app, first_headers = admin_app
    assert (
        first.patch(
            "/api/v1/users/" + str(first_user.user_id), json=change, headers=first_headers
        ).status_code
        == 409
    )
    other = add_user(first, first_headers, "other-admin", "admin").json()
    with TestClient(app, base_url=ORIGIN) as second:
        second_headers = ready_user(second, "other-admin")
        calls = [
            (first, str(first_user.user_id), first_headers),
            (second, other["id"], second_headers),
        ]

        def update(item):
            client, user_id, headers = item
            return client.patch(
                "/api/v1/users/" + user_id, json=change, headers=headers
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(update, calls))
        assert sorted(statuses) == [200, 409]
    with database.transaction() as transaction:
        assert (
            transaction.execute(
                text("SELECT count(*) FROM users WHERE enabled AND role='admin'")
            ).scalar_one()
            == 1
        )


def test_audit_redaction(admin_app):
    client, database, _, _, headers = admin_app
    created = add_user(client, headers)
    with database.transaction() as transaction:
        rows = (
            transaction.execute(
                text(
                    "SELECT actor_id,action,resource_id,outcome,request_id,timestamp FROM audit_events ORDER BY timestamp"
                )
            )
            .mappings()
            .all()
        )
        event = rows[-1]
        assert event["action"] == "user.create" and event["outcome"] == "succeeded"
        assert str(event["request_id"]) == created.headers["x-request-id"]
        assert str(event["resource_id"]) == created.json()["id"]
        assert PASSWORD not in json.dumps([dict(row) for row in rows], default=str)


def test_audit_failure_rolls_back_user_change(admin_app, monkeypatch):
    from app.modules.audit.service import AuditService

    client, database, _, _, headers = admin_app

    def unavailable(*args, **kwargs):
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(AuditService, "record", unavailable)
    assert add_user(client, headers, "not-committed").status_code == 500
    with database.transaction() as transaction:
        assert (
            transaction.execute(
                text("SELECT count(*) FROM users WHERE username='not-committed'")
            ).scalar_one()
            == 0
        )
