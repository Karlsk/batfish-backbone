from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

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
from tests.test_users import add_user, ready_user

pytestmark = pytest.mark.integration


@pytest.fixture
def concern_app(request):
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
    headers = write_headers(login(client, password=NEW_PASSWORD).json())
    return client, database, user, app, headers


def network(database, user_id):
    network_id = uuid4()
    with database.transaction() as transaction:
        transaction.execute(
            text(
                "INSERT INTO networks(id, display_name, engine_name, sync_state, created_by) "
                "VALUES (:id, 'Team network', :engine, 'ready', :user)"
            ),
            {"id": network_id, "engine": f"test-{network_id.hex}", "user": user_id},
        )
    return network_id


def body(network_id):
    return {
        "network_id": str(network_id),
        "name": "支付核心链路",
        "description": "团队确认的关键流量",
        "priority": "high",
        "flows": [
            {
                "start_location": "r1",
                "destination_ip": "10.0.0.2",
                "source_ip": "10.0.0.1",
                "protocol": "tcp",
                "destination_port": 443,
            }
        ],
    }


def test_admin_versions_are_immutable_and_member_can_read(concern_app):
    admin, database, user, app, headers = concern_app
    network_id = network(database, user.user_id)
    created = admin.post("/api/v1/business-concerns", json=body(network_id), headers=headers)
    assert created.status_code == 201, created.text
    concern = created.json()
    assert concern["version"] == 1 and concern["archived"] is False
    assert concern["network_id"] == str(network_id)
    assert concern["flows"] == body(network_id)["flows"]
    identifier = concern["id"]

    assert add_user(admin, headers, "concern-member").status_code == 201
    with TestClient(app, base_url=ORIGIN) as member:
        member_headers = ready_user(member, "concern-member")
        page = member.get("/api/v1/business-concerns", params={"network_id": str(network_id)})
        assert page.status_code == 200 and page.json()["items"] == [concern]
        assert page.json()["total"] == 1
        assert member.get(f"/api/v1/business-concerns/{identifier}").json() == concern
        assert (
            member.patch(
                f"/api/v1/business-concerns/{identifier}",
                json={"expected_version": 1, "priority": "low"},
                headers=member_headers,
            ).status_code
            == 403
        )
        assert (
            member.post(
                "/api/v1/business-concerns", json=body(network_id), headers=member_headers
            ).status_code
            == 403
        )

    updated = admin.patch(
        f"/api/v1/business-concerns/{identifier}",
        json={"expected_version": 1, "name": "支付链路", "priority": "medium"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2 and updated.json()["name"] == "支付链路"
    previous = admin.get(f"/api/v1/business-concerns/{identifier}", params={"version": 1})
    assert previous.status_code == 200 and previous.json() == concern
    assert (
        admin.patch(
            f"/api/v1/business-concerns/{identifier}",
            json={"expected_version": 1, "priority": "low"},
            headers=headers,
        ).status_code
        == 409
    )
    assert admin.get(f"/api/v1/business-concerns/{identifier}").json()["version"] == 2

    archived = admin.patch(
        f"/api/v1/business-concerns/{identifier}",
        json={"expected_version": 2, "archived": True},
        headers=headers,
    )
    assert archived.status_code == 200 and archived.json()["version"] == 3
    assert admin.get("/api/v1/business-concerns").json()["total"] == 0
    assert (
        admin.get("/api/v1/business-concerns", params={"include_archived": True}).json()["items"][
            0
        ]["id"]
        == identifier
    )
    assert (
        admin.get(f"/api/v1/business-concerns/{identifier}", params={"version": 1}).json()
        == concern
    )
    with database.transaction() as transaction:
        audit = transaction.execute(
            text("SELECT action, outcome FROM audit_events WHERE resource_id=:id"),
            {"id": identifier},
        ).all()
    assert set(audit) == {
        ("business_concern.create", "created"),
        ("business_concern.update", "updated"),
        ("business_concern.archive", "archived"),
    }


def test_validation_and_network_boundary(concern_app):
    client, database, user, _, headers = concern_app
    network_id = network(database, user.user_id)
    route = "/api/v1/business-concerns"
    assert client.get(route).status_code == 200
    assert client.post(route, json=body(network_id)).status_code == 403
    assert client.post(route, json=body(uuid4()), headers=headers).status_code == 404
    good = body(network_id)
    invalid = [
        good | {"engine_name": "forbidden"},
        good | {"flows": []},
        good | {"flows": good["flows"] * 11},
        good | {"flows": [{"start_location": "r1", "destination_ip": "10.0.0.999"}]},
        good | {"flows": [{"start_location": "r1", "destination_ip": "10.0.00.2"}]},
        good
        | {
            "flows": [
                {"start_location": "r1", "destination_ip": "10.0.0.2", "source_ip": "999.0.0.1"}
            ]
        },
        good
        | {
            "flows": [
                {
                    "start_location": "r1",
                    "destination_ip": "10.0.0.2",
                    "protocol": "icmp",
                    "destination_port": 443,
                }
            ]
        },
        good
        | {
            "flows": [
                {
                    "start_location": "r1",
                    "destination_ip": "10.0.0.2",
                    "protocol": "tcp",
                    "destination_port": 65536,
                }
            ]
        },
    ]
    for request in invalid:
        assert client.post(route, json=request, headers=headers).status_code == 422
    created = client.post(route, json=good, headers=headers)
    assert created.status_code == 201
    identifier = created.json()["id"]
    for patch in [
        {},
        {"expected_version": 1},
        {"expected_version": 1, "network_id": str(uuid4())},
        {"expected_version": 1, "flows": []},
    ]:
        assert client.patch(f"{route}/{identifier}", json=patch, headers=headers).status_code == 422
    assert client.get(f"{route}/{uuid4()}").status_code == 404
    assert client.get(f"{route}/{identifier}", params={"version": 99}).status_code == 404
    second = client.post(route, json=good | {"name": "账务链路"}, headers=headers)
    assert second.status_code == 201
    page = client.get(route, params={"network_id": str(network_id), "offset": 1, "limit": 1})
    assert page.status_code == 200 and page.json()["total"] == 2
    assert len(page.json()["items"]) == 1
    for params in [{"limit": 201}, {"offset": -1}]:
        assert client.get(route, params=params).status_code == 422


def test_concurrent_updates_with_same_version_have_one_winner(concern_app):
    first, database, user, app, first_headers = concern_app
    network_id = network(database, user.user_id)
    created = first.post("/api/v1/business-concerns", json=body(network_id), headers=first_headers)
    assert created.status_code == 201
    identifier = created.json()["id"]
    with TestClient(app, base_url=ORIGIN) as second:
        second_headers = write_headers(login(second, password=NEW_PASSWORD).json())

        def update(client, headers, priority):
            return client.patch(
                f"/api/v1/business-concerns/{identifier}",
                json={"expected_version": 1, "priority": priority},
                headers=headers,
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(update, first, first_headers, "medium")
            b = pool.submit(update, second, second_headers, "low")
            assert sorted([a.result(), b.result()]) == [200, 409]
    current = first.get(f"/api/v1/business-concerns/{identifier}").json()
    assert current["version"] == 2 and current["priority"] in {"medium", "low"}
    assert (
        first.get(f"/api/v1/business-concerns/{identifier}", params={"version": 1}).json()
        == created.json()
    )
