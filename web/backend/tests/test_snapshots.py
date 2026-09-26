from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.contracts.errors import ServiceError
from tests import test_networks
from tests.test_networks import create_network
from tests.test_uploads import upload

pytestmark = pytest.mark.integration
snapshot_app = test_networks.network_app


def setup(snapshot_app):
    client, db, app, headers = snapshot_app
    network = create_network(client, headers).json()["id"]
    source = upload(client, headers, network).json()
    actor = app.state.auth_service.require_actor(client.cookies.get("batfish_session"))
    return client, db, app, headers, network, source, actor


def create(client, headers, network, source, **kw):
    return client.post(
        f"/api/v1/networks/{network}/snapshots",
        headers=headers,
        json={"display_name": "Same", "upload_id": source["id"], **kw},
    )


def test_snapshot_idempotency_and_overwrite_impossible(snapshot_app):
    client, db, app, headers, network, source, actor = setup(snapshot_app)
    headers = headers | {"Idempotency-Key": uuid4().hex}
    first = create(client, headers, network, source)
    assert first.status_code == 202
    assert create(client, headers, network, source).json() == first.json()
    assert create(client, headers, network, source, display_name="Changed").status_code == 409
    second_source = upload(client, headers, network).json()
    second = create(client, headers | {"Idempotency-Key": uuid4().hex}, network, second_source)
    assert second.status_code == 202
    rows = client.get(f"/api/v1/networks/{network}/snapshots").json()["items"]
    assert len(rows) == 2 and len({r["engine_name"] for r in rows}) == 2
    assert all(r["status"] == "queued" for r in rows)


def test_succeeded_job_does_not_make_earlier_queued_snapshot_read_look_failed(
    snapshot_app, monkeypatch
):
    client, db, app, headers, network, source, actor = setup(snapshot_app)
    created = create(client, headers, network, source).json()
    service = app.state.snapshots_service
    original_get = service._jobs.get

    def completed_job(actor, job_id):
        return original_get(actor, job_id).model_copy(update={"status": "succeeded"})

    monkeypatch.setattr(service._jobs, "get", completed_job)
    response = client.get(f"/api/v1/networks/{network}/snapshots/{created['snapshot_id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "initializing"


def test_upload_consumed_once_atomic(snapshot_app):
    from app.modules.snapshots.schemas import CreateSnapshotRequest

    client, db, app, headers, network, source, actor = setup(snapshot_app)
    request = CreateSnapshotRequest(display_name="Concurrent", upload_id=source["id"])

    def attempt():
        try:
            app.state.snapshots_service.create(actor, UUID(network), request)
            return "created"
        except ServiceError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == ["CONFLICT", "created"]
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM snapshots")).scalar_one() == 1
        assert tx.execute(text("SELECT count(*) FROM jobs")).scalar_one() == 1


def test_snapshot_queue_failure_rolls_back_consumption(snapshot_app, monkeypatch):
    client, db, app, headers, network, source, actor = setup(snapshot_app)
    from app.modules.jobs.service import JobsService

    def fail(*args, **kwargs):
        raise RuntimeError("private details")

    with monkeypatch.context() as patch:
        patch.setattr(JobsService, "submit", fail)
        response = create(client, headers, network, source)
    assert response.status_code == 500 and "private" not in response.text
    with db.transaction() as tx:
        assert tx.execute(text("SELECT consumed_at FROM uploads")).scalar_one() is None
        assert tx.execute(text("SELECT count(*) FROM snapshots")).scalar_one() == 0
    assert create(client, headers, network, source).status_code == 202


def test_cancel_and_retry_initialization(snapshot_app):
    client, db, app, headers, network, source, actor = setup(snapshot_app)
    first = create(client, headers, network, source).json()
    assert (
        client.post("/api/v1/jobs/" + first["job_id"] + "/cancel", headers=headers).status_code
        == 200
    )
    detail = client.get(f"/api/v1/networks/{network}/snapshots/{first['snapshot_id']}").json()
    assert detail["status"] == "failed"
    with pytest.raises(ServiceError):
        app.state.snapshots_service.require_analyzable(
            actor, UUID(network), UUID(first["snapshot_id"])
        )
    key = uuid4().hex
    retry = client.post(
        "/api/v1/jobs/" + first["job_id"] + "/retry", headers=headers | {"Idempotency-Key": key}
    )
    assert retry.status_code == 202
    new = retry.json()
    assert (
        new["id"] != first["job_id"] and new["resource_ids"]["snapshot_id"] != first["snapshot_id"]
    )
    assert new["context"]["engine_snapshot"] != detail["engine_name"]
    assert (
        client.post(
            "/api/v1/jobs/" + first["job_id"] + "/retry", headers=headers | {"Idempotency-Key": key}
        ).json()
        == new
    )
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM uploads")).scalar_one() == 1
        assert tx.execute(text("SELECT count(*) FROM snapshots")).scalar_one() == 2


def test_snapshot_options_and_network_boundary(snapshot_app):
    client, db, app, headers, network, source, actor = setup(snapshot_app)
    for options in [{"overwrite": True}, {"host": "elsewhere"}, {"parse_reuse": "yes"}]:
        assert create(client, headers, network, source, options=options).status_code == 422
    other = create_network(client, headers).json()["id"]
    assert create(client, headers, other, source).status_code == 404


@pytest.mark.parametrize(
    "fixture_name,warning",
    [("small_network", False), ("cisco_four", False), ("small_network", True)],
)
def test_real_snapshot_initialization_quality(snapshot_app, fixture_name, warning):
    from pathlib import Path

    client, db, app, headers, network, source, actor = setup(snapshot_app)
    configs = Path(__file__).parent / "fixtures" / fixture_name / "configs"
    files = [(p.name, p.read_bytes()) for p in sorted(configs.iterdir())]
    if warning:
        files[0] = (
            files[0][0],
            files[0][1].replace(b"return", b"mvp10-unsupported-command\nreturn"),
        )
    source = upload(client, headers, network, files=files).json()
    queued = create(
        client,
        headers,
        network,
        source,
        options={"ignore_management_interfaces": False, "parse_reuse": True},
    ).json()
    assert app.state.execution_service.run_once("snapshot-test-worker")
    job = client.get("/api/v1/jobs/" + queued["job_id"]).json()
    assert job["status"] == "succeeded", job
    detail = client.get(f"/api/v1/networks/{network}/snapshots/{queued['snapshot_id']}").json()
    assert detail["status"] == ("ready_with_warnings" if warning else "ready"), detail
    assert detail["quality_summary"]["node_count"] == (2 if fixture_name == "small_network" else 4)
    assert detail["engine_version"] == "0.36.0" and detail["sdk_version"] == "2026.9.17.3748"
    context = app.state.snapshots_service.require_analyzable(
        actor, UUID(network), UUID(queued["snapshot_id"])
    )
    assert context.engine_version == detail["engine_version"]
    if warning:
        assert "PARTIALLY_UNRECOGNIZED" in detail["quality_summary"]["parse_statuses"]
    # Reusing a display label creates a fresh remote snapshot and leaves the first analyzable.
    another = upload(client, headers, network, files=files).json()
    second = create(client, headers, network, another).json()
    assert app.state.execution_service.run_once("snapshot-test-worker")
    assert second["snapshot_id"] != queued["snapshot_id"]
    assert client.get("/api/v1/jobs/" + second["job_id"]).json()["status"] == "succeeded"
    assert (
        app.state.snapshots_service.require_analyzable(
            actor, UUID(network), UUID(queued["snapshot_id"])
        )
        == context
    )


def test_failed_initialization_retains_input(snapshot_app, monkeypatch):
    from app.modules.snapshots.schemas import InitializationAnswer

    client, db, app, headers, network, source, actor = setup(snapshot_app)
    queued = create(client, headers, network, source).json()
    service = app.state.snapshots_service
    monkeypatch.setattr(
        service._controller,
        "initialize",
        lambda *args: InitializationAnswer(
            parse_status=({"Status": "FAILED", "Nodes": []},),
            issues=(),
            engine_version="test",
            sdk_version="test",
        ),
    )
    assert app.state.execution_service.run_once("worker")
    job = client.get("/api/v1/jobs/" + queued["job_id"]).json()
    assert job["status"] == "failed" and job["error"]["code"] == "NOT_READY"
    detail = client.get(f"/api/v1/networks/{network}/snapshots/{queued['snapshot_id']}").json()
    assert detail["status"] == "failed" and detail["quality_summary"]["parse_statuses"] == [
        "FAILED"
    ]
    assert (
        app.state.uploads_service.storage_root
        / source["storage_key"]
        / source["manifest"]["files"][0]["id"]
    ).exists()
    with pytest.raises(ServiceError):
        service.require_analyzable(actor, UUID(network), UUID(queued["snapshot_id"]))


def test_interrupted_snapshot_retry_after_reconciliation(snapshot_app):
    client, db, app, headers, network, source, actor = setup(snapshot_app)
    queued = create(client, headers, network, source).json()
    job = app.state.jobs_service.claim("worker")
    app.state.jobs_service.interrupt(job.id, "worker")
    assert (
        client.post("/api/v1/jobs/" + queued["job_id"] + "/retry", headers=headers).status_code
        == 503
    )
    # No worker lease exists; reconcile through the public administration service.
    response = client.post(
        "/api/v1/admin/engine/reconcile",
        headers=headers,
        json={"resolution": "confirmed_idle", "note": "Test worker stopped before SDK invocation"},
    )
    assert response.status_code == 200
    assert (
        client.post("/api/v1/jobs/" + queued["job_id"] + "/retry", headers=headers).status_code
        == 202
    )
