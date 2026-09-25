from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.contracts.dto import ExecutionContext
from app.contracts.errors import ServiceError
from app.infrastructure.settings import Settings
from app.modules.jobs.service import JobsService
from tests import test_networks
from tests.test_auth import ORIGIN
from tests.test_networks import create_network
from tests.test_users import add_user, ready_user

pytestmark = pytest.mark.integration
job_app = test_networks.network_app


def prepare(job_app):
    client, db, app, headers = job_app
    network = create_network(client, headers).json()
    context = ExecutionContext(
        network_id=network["id"],
        engine_network=network["engine_name"],
        engine_version="0.36.0",
        sdk_version="2026.9.17.3748",
        schema_version="1",
    )
    actor = app.state.auth_service.require_actor(client.cookies.get("batfish_session"))
    return client, db, app, headers, actor, context


def submit(service, actor, context, *, key=None, parameters=None, kind="analysis"):
    return service.submit(
        actor,
        kind,
        context,
        parameters or {"question": "nodes", "options": {"nodes": ["r1"]}},
        key or uuid4().hex,
    )


def test_idempotent_submission_and_immutable_inputs(job_app):
    _, db, app, _, actor, context = prepare(job_app)
    service = app.state.jobs_service
    parameters = {"question": "nodes", "options": {"nodes": ["r1"]}}
    key = uuid4().hex
    first = submit(service, actor, context, key=key, parameters=parameters)
    replay = submit(service, actor, context, key=key, parameters=parameters)
    assert first == replay and first.status == "queued" and first.cancel_allowed
    parameters["options"]["nodes"].append("r2")
    assert service.get(actor, first.id).requested_parameters["options"]["nodes"] == ("r1",)
    with pytest.raises(TypeError):
        first.requested_parameters["options"]["nodes"][0] = "r3"
    assert first.context == context and first.retry_of is None
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM jobs")).scalar_one() == 1
        assert (
            tx.execute(
                text("SELECT job_id FROM idempotency_records WHERE job_id IS NOT NULL")
            ).scalar_one()
            == first.id
        )


def test_idempotency_payload_conflict_and_user_scope(job_app):
    client, _, app, headers, actor, context = prepare(job_app)
    service = app.state.jobs_service
    key = uuid4().hex
    first = submit(service, actor, context, key=key)
    with pytest.raises(ServiceError) as error:
        submit(service, actor, context, key=key, parameters={"question": "routes"})
    assert error.value.code == "CONFLICT"
    add_user(client, headers, "member")
    with TestClient(app, base_url=ORIGIN) as member:
        ready_user(member, "member")
        second_actor = app.state.auth_service.require_actor(member.cookies.get("batfish_session"))
        assert submit(service, second_actor, context, key=key).id != first.id


def test_queue_limit_concurrent_and_idempotent_replay(job_app):
    _, db, app, _, actor, context = prepare(job_app)
    service = JobsService(
        db, app.state.auth_service, Settings(max_queued_jobs_per_user=2, max_queued_jobs_global=3)
    )
    key = uuid4().hex
    first = submit(service, actor, context, key=key)

    def attempt(_):
        try:
            return submit(service, actor, context).id
        except ServiceError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=4) as executor:
        outcomes = list(executor.map(attempt, range(4)))
    assert outcomes.count("RATE_LIMITED") == 3
    assert submit(service, actor, context, key=key).id == first.id
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM jobs")).scalar_one() == 2
        assert (
            tx.execute(
                text("SELECT count(*) FROM idempotency_records WHERE route LIKE :route"),
                {"route": "/jobs/%"},
            ).scalar_one()
            == 2
        )


def test_cancel_race(job_app):
    _, db, app, _, actor, context = prepare(job_app)
    service = app.state.jobs_service
    job = submit(service, actor, context)

    def claim():
        with db.transaction() as tx:
            return tx.execute(
                text(
                    "UPDATE jobs SET status='running', cancel_allowed=false WHERE id=:id AND status='queued' RETURNING id"
                ),
                {"id": job.id},
            ).scalar_one_or_none()

    def cancel():
        try:
            return service.cancel(actor, job.id).status
        except ServiceError as error:
            assert error.code == "CONFLICT"
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        a, b = executor.submit(claim), executor.submit(cancel)
        claimed, cancelled = a.result(), b.result()
    assert (claimed is not None and cancelled == "conflict") or (
        claimed is None and cancelled == "cancelled"
    )
    current = service.get(actor, job.id)
    assert current.status in {"running", "cancelled"} and not current.cancel_allowed


def test_cancel_permissions_deletion_and_shared_history(job_app):
    client, _, app, headers, admin, context = prepare(job_app)
    add_user(client, headers, "owner")
    add_user(client, headers, "other")
    service = app.state.jobs_service
    with TestClient(app, base_url=ORIGIN) as owner, TestClient(app, base_url=ORIGIN) as other:
        owner_headers = ready_user(owner, "owner")
        other_headers = ready_user(other, "other")
        actor = app.state.auth_service.require_actor(owner.cookies.get("batfish_session"))
        job = submit(service, actor, context)
        assert other.get("/api/v1/jobs/" + str(job.id)).status_code == 200
        assert (
            other.post("/api/v1/jobs/" + str(job.id) + "/cancel", headers=other_headers).status_code
            == 403
        )
        assert (
            owner.post("/api/v1/jobs/" + str(job.id) + "/cancel", headers=owner_headers).json()[
                "status"
            ]
            == "cancelled"
        )
        assert (
            owner.post("/api/v1/jobs/" + str(job.id) + "/cancel", headers=owner_headers).status_code
            == 409
        )
        another = submit(service, actor, context)
        assert (
            client.post("/api/v1/jobs/" + str(another.id) + "/cancel", headers=headers).status_code
            == 200
        )
    deletion = submit(service, admin, context, kind="deletion")
    assert not deletion.cancel_allowed
    assert (
        client.post("/api/v1/jobs/" + str(deletion.id) + "/cancel", headers=headers).status_code
        == 409
    )
    page = client.get(
        "/api/v1/jobs",
        params={
            "network_id": str(context.network_id),
            "status": "cancelled",
            "created_by": str(actor.user_id),
            "limit": 1,
        },
    ).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert client.get("/api/v1/jobs", params={"status": "bogus"}).status_code == 422
    assert client.get("/api/v1/jobs/" + str(uuid4())).status_code == 404


def test_disabled_creator_cannot_submit_or_cancel(job_app):
    client, _, app, headers, _, context = prepare(job_app)
    created = add_user(client, headers, "member")
    with TestClient(app, base_url=ORIGIN) as member:
        ready_user(member, "member")
        actor = app.state.auth_service.require_actor(member.cookies.get("batfish_session"))
        job = submit(app.state.jobs_service, actor, context)
        assert (
            client.patch(
                "/api/v1/users/" + created.json()["id"], json={"enabled": False}, headers=headers
            ).status_code
            == 200
        )
        for operation in [
            lambda: submit(app.state.jobs_service, actor, context),
            lambda: app.state.jobs_service.cancel(actor, job.id),
        ]:
            with pytest.raises(ServiceError) as error:
                operation()
            assert error.value.code == "UNAUTHORIZED"


def test_global_queue_limit_across_users(job_app):
    client, db, app, headers, admin, context = prepare(job_app)
    service = JobsService(
        db, app.state.auth_service, Settings(max_queued_jobs_per_user=10, max_queued_jobs_global=1)
    )
    submit(service, admin, context)
    add_user(client, headers, "member")
    with TestClient(app, base_url=ORIGIN) as member:
        ready_user(member, "member")
        actor = app.state.auth_service.require_actor(member.cookies.get("batfish_session"))
        with pytest.raises(ServiceError) as error:
            submit(service, actor, context)
        assert error.value.code == "RATE_LIMITED" and error.value.retryable
        assert service.list(actor).total == 1


def test_simultaneous_same_key_does_not_duplicate(job_app):
    _, _, app, _, actor, context = prepare(job_app)
    key = uuid4().hex
    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(
            executor.map(
                lambda _: submit(app.state.jobs_service, actor, context, key=key).id, range(4)
            )
        )
    assert len(set(ids)) == 1
    assert app.state.jobs_service.list(actor).total == 1


def test_job_submission_rejects_invalid_inputs_and_member_delete(job_app):
    client, _, app, headers, actor, context = prepare(job_app)
    for key in ["", "bad key", "x" * 129]:
        with pytest.raises(ServiceError) as error:
            app.state.jobs_service.submit(actor, "analysis", context, {}, key)
        assert error.value.code == "VALIDATION_ERROR"
    with pytest.raises(ServiceError):
        app.state.jobs_service.submit(actor, "execute-python", context, {}, uuid4().hex)
    add_user(client, headers, "member")
    with TestClient(app, base_url=ORIGIN) as member:
        ready_user(member, "member")
        member_actor = app.state.auth_service.require_actor(member.cookies.get("batfish_session"))
        with pytest.raises(ServiceError) as error:
            submit(app.state.jobs_service, member_actor, context, kind="deletion")
        assert error.value.code == "FORBIDDEN"
