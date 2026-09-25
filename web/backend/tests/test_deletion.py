from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import text

from app.contracts.errors import ServiceError
from tests import test_networks
from tests.test_snapshots import create, setup
from tests.test_uploads import upload

pytestmark = pytest.mark.integration
deletion_app = test_networks.network_app


def ready(deletion_app, fixture="small_network"):
    client, db, app, headers, network, source, actor = setup(deletion_app)
    folder = Path(__file__).parent / "fixtures" / fixture / "configs"
    source = upload(
        client, headers, network, files=[(p.name, p.read_bytes()) for p in folder.iterdir()]
    ).json()
    created = create(client, headers, network, source).json()
    assert app.state.execution_service.run_once("worker")
    return client, db, app, headers, network, source, actor, created


def test_nonempty_network_delete(deletion_app):
    client, db, app, headers, network, source, actor = setup(deletion_app)
    created = create(client, headers, network, source).json()
    assert client.delete(f"/api/v1/networks/{network}", headers=headers).status_code == 409
    assert (
        client.delete(
            f"/api/v1/networks/{network}/snapshots/{created['snapshot_id']}", headers=headers
        ).status_code
        == 409
    )
    assert app.state.jobs_service.get(actor, UUID(created["job_id"])).status == "queued"


@pytest.mark.parametrize("fixture", ["small_network", "cisco_four"])
def test_real_delete_preserves_result_and_tombstone(deletion_app, fixture):
    client, db, app, headers, network, source, actor, created = ready(deletion_app, fixture)
    analysis = app.state.analysis_service.submit(
        actor, UUID(network), UUID(created["snapshot_id"]), "nodes", {}
    )
    assert app.state.execution_service.run_once("worker")
    result = app.state.jobs_service.get(actor, analysis.id).result_id
    url = f"/api/v1/networks/{network}/snapshots/{created['snapshot_id']}"
    deleted = client.delete(url, headers=headers)
    assert deleted.status_code == 202, deleted.text
    job = deleted.json()
    assert job["kind"] == "deletion" and not job["cancel_allowed"]
    assert client.get(url).json()["status"] == "deleting"
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel", headers=headers).status_code == 409
    assert client.post(url + "/analyses/nodes", headers=headers, json={}).status_code in {409, 503}
    assert app.state.execution_service.run_once("worker")
    assert app.state.jobs_service.get(actor, UUID(job["id"])).status == "succeeded"
    assert client.get(url).json()["status"] == "deleted"
    assert client.get(url + "/files").status_code == 404
    assert (
        client.get(f"/api/v1/results/{result}/export").json()["metadata"]["context"]["snapshot_id"]
        == created["snapshot_id"]
    )
    assert not (app.state.uploads_service.storage_root / source["storage_key"]).exists()
    response = client.delete(f"/api/v1/networks/{network}", headers=headers)
    assert response.status_code == 202
    assert app.state.execution_service.run_once("worker")
    assert client.get(f"/api/v1/networks/{network}").status_code == 404
    assert client.get(f"/api/v1/results/{result}").status_code == 200
    with db.transaction() as tx:
        assert (
            tx.execute(
                text("SELECT count(*) FROM audit_events WHERE action='resource.delete'")
            ).scalar_one()
            == 2
        )


def test_delete_submit_race(deletion_app):
    client, db, app, headers, network, source, actor, created = ready(deletion_app)
    barrier = Barrier(2)

    def attempt(delete):
        barrier.wait(timeout=5)
        try:
            if delete:
                app.state.lifecycle_service.delete(
                    actor, UUID(network), UUID(created["snapshot_id"])
                )
            else:
                app.state.analysis_service.submit(
                    actor, UUID(network), UUID(created["snapshot_id"]), "nodes", {}
                )
            return "delete" if delete else "analysis"
        except ServiceError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [True, False]))
    assert len(set(outcomes) & {"delete", "analysis"}) == 1, outcomes
    with db.transaction() as tx:
        queued = tx.execute(text("SELECT kind FROM jobs WHERE status='queued'")).scalars().all()
        assert queued in [["analysis"], ["deletion"]]


def test_delete_sdk_writeback_failure(deletion_app, monkeypatch):
    from app.modules.snapshots.repository import SnapshotsRepository

    client, db, app, headers, network, source, actor, created = ready(deletion_app)
    url = f"/api/v1/networks/{network}/snapshots/{created['snapshot_id']}"
    job = client.delete(url, headers=headers).json()
    with monkeypatch.context() as patch:
        patch.setattr(
            SnapshotsRepository,
            "finish_deletion",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("writeback failed")),
        )
        assert app.state.execution_service.run_once("worker")
    assert client.get(url).json()["status"] == "deleting"
    assert (app.state.uploads_service.storage_root / source["storage_key"]).exists()
    assert client.post(f"/api/v1/jobs/{job['id']}/retry", headers=headers).status_code == 409
    response = client.post(
        f"/api/v1/admin/deletions/{job['id']}/reconcile",
        headers=headers,
        json={"note": "Verify fixed remote snapshot after database writeback failure"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "deleted"
    assert client.get(url).json()["status"] == "deleted"


def test_member_cannot_delete_or_reconcile(deletion_app):
    from fastapi.testclient import TestClient

    from tests.test_auth import ORIGIN
    from tests.test_users import add_user, ready_user

    client, db, app, headers, network, source, actor = setup(deletion_app)
    add_user(client, headers, "reader")
    with TestClient(app, base_url=ORIGIN) as member:
        member_headers = ready_user(member, "reader")
        assert (
            member.delete(f"/api/v1/networks/{network}", headers=member_headers).status_code == 403
        )
        assert (
            member.post(
                "/api/v1/admin/deletions/00000000-0000-0000-0000-000000000000/reconcile",
                headers=member_headers,
                json={"note": "Member must not reconcile"},
            ).status_code
            == 403
        )


def test_unknown_and_existing_remote_recovery(deletion_app, monkeypatch):
    from app.infrastructure.engine import EngineGate
    from app.modules.snapshots.controller import SnapshotController

    client, db, app, headers, network, source, actor, created = ready(deletion_app)
    url = f"/api/v1/networks/{network}/snapshots/{created['snapshot_id']}"
    job = client.delete(url, headers=headers).json()

    def fail(*args, **kwargs):
        with db.transaction() as tx:
            EngineGate(db).mark_unknown(transaction=tx)
        raise TimeoutError("Remote outcome unknown")

    with monkeypatch.context() as patch:
        patch.setattr(SnapshotController, "deletion_presence", fail)
        assert app.state.execution_service.run_once("worker")
    recovery = f"/api/v1/admin/deletions/{job['id']}/reconcile"
    assert (
        client.post(
            recovery, headers=headers, json={"note": "No evidence of idle engine yet"}
        ).status_code
        == 409
    )
    assert client.get(url).json()["status"] == "deleting"
    assert client.delete(url, headers=headers).status_code == 409
    response = client.post(
        "/api/v1/admin/engine/reconcile",
        headers=headers,
        json={
            "resolution": "confirmed_idle",
            "note": "Controlled fault occurred before SDK request; owned worker stopped",
        },
    )
    assert response.status_code == 200, response.text
    response = client.post(
        recovery,
        headers=headers,
        json={"note": "Check actual fixed-name remote object after global reconciliation"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"] in {"ready", "ready_with_warnings"}
    assert (app.state.uploads_service.storage_root / source["storage_key"]).exists()
    # An old reconciliation must not alter a newly bound deletion.
    newer = client.delete(url, headers=headers)
    assert newer.status_code == 202
    assert (
        client.post(
            recovery,
            headers=headers,
            json={"note": "Old deletion must not override the current operation"},
        ).status_code
        == 409
    )


def test_delete_initialization_submit_race(deletion_app):
    client, db, app, headers, network, source, actor = setup(deletion_app)
    from app.modules.snapshots.schemas import CreateSnapshotRequest

    barrier = Barrier(2)

    def attempt(delete):
        barrier.wait(timeout=5)
        try:
            if delete:
                app.state.lifecycle_service.delete(actor, UUID(network))
            else:
                app.state.snapshots_service.create(
                    actor,
                    UUID(network),
                    CreateSnapshotRequest(display_name="Race", upload_id=UUID(source["id"])),
                )
            return "delete" if delete else "initialization"
        except ServiceError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [True, False]))
    assert len(set(outcomes) & {"delete", "initialization"}) == 1, outcomes


def test_delete_keeps_shared_retry_input_until_last_snapshot(deletion_app):
    client, db, app, headers, network, source, actor = setup(deletion_app)
    first = create(client, headers, network, source).json()
    app.state.jobs_service.cancel(actor, UUID(first["job_id"]))
    retry = app.state.execution_service.retry(actor, UUID(first["job_id"]))
    assert app.state.execution_service.run_once("worker")
    url = f"/api/v1/networks/{network}/snapshots/"
    old = client.delete(url + first["snapshot_id"], headers=headers)
    assert old.status_code == 202
    assert app.state.execution_service.run_once("worker")
    path = app.state.uploads_service.storage_root / source["storage_key"]
    assert path.exists()
    assert client.post(f"/api/v1/jobs/{first['job_id']}/retry", headers=headers).status_code == 409
    assert client.delete(url + str(retry.context.snapshot_id), headers=headers).status_code == 202
    assert app.state.execution_service.run_once("worker")
    assert not path.exists()


def test_late_network_creation_retry_cannot_resurrect_deleted_network(deletion_app, monkeypatch):
    from contextlib import contextmanager
    from threading import Event, current_thread
    from uuid import uuid4

    from app.infrastructure.engine import EngineGate
    from app.modules.networks.schemas import CreateNetworkRequest
    from tests.test_networks import create_network

    client, db, app, headers = deletion_app
    actor = app.state.auth_service.require_actor(client.cookies.get("batfish_session"))
    key = uuid4().hex
    with EngineGate(db).exclusive(owner="seed-pending"):
        assert create_network(client, headers, key=key).status_code == 503
    network = client.get("/api/v1/networks").json()["items"][0]
    waiting, release = Event(), Event()
    original = app.state.jobs_service.resource_boundary

    @contextmanager
    def delayed_boundary():
        if current_thread().name.startswith("stale-create"):
            waiting.set()
            assert release.wait(timeout=10)
        with original() as tx:
            yield tx

    monkeypatch.setattr(app.state.jobs_service, "resource_boundary", delayed_boundary)

    def retry():
        try:
            app.state.networks_service.create(
                actor, CreateNetworkRequest(display_name="Lab"), idempotency_key=key
            )
            return "created"
        except ServiceError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="stale-create") as pool:
        future = pool.submit(retry)
        try:
            assert waiting.wait(timeout=5)
            assert create_network(client, headers, key=key).status_code == 201
            deleted = client.delete(f"/api/v1/networks/{network['id']}", headers=headers)
            assert deleted.status_code == 202
            assert app.state.execution_service.run_once("worker")
        finally:
            release.set()
        assert future.result(timeout=5) == "NOT_FOUND"
    assert client.get(f"/api/v1/networks/{network['id']}").status_code == 404
    job = app.state.jobs_service.get(actor, UUID(deleted.json()["id"]))
    assert app.state.networks_service.deletion_presence(job) is False


def test_reference_snapshot_is_protected_by_active_job(deletion_app):
    client, db, app, headers, network, source, actor, first = ready(deletion_app)
    folder = Path(__file__).parent / "fixtures" / "small_network" / "configs"
    extra = upload(
        client, headers, network, files=[(p.name, p.read_bytes()) for p in folder.iterdir()]
    ).json()
    second = create(client, headers, network, extra).json()
    assert app.state.execution_service.run_once("worker")
    context = app.state.snapshots_service.require_analyzable(
        actor, UUID(network), UUID(second["snapshot_id"])
    )
    reference = app.state.snapshots_service.get(actor, UUID(network), UUID(first["snapshot_id"]))
    context = context.model_copy(
        update={
            "reference_snapshot_id": reference.id,
            "engine_reference_snapshot": reference.engine_name,
        }
    )
    app.state.jobs_service.submit(actor, "analysis", context, {})
    assert (
        client.delete(
            f"/api/v1/networks/{network}/snapshots/{first['snapshot_id']}", headers=headers
        ).status_code
        == 409
    )
