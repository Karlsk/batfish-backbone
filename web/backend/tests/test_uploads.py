from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.contracts.errors import ServiceError
from tests import test_networks
from tests.test_auth import ORIGIN
from tests.test_networks import create_network
from tests.test_upload_archives import zipped
from tests.test_users import add_user, ready_user

pytestmark = pytest.mark.integration
upload_app = test_networks.network_app


def upload(client, headers, network, *, files=None, archive=None):
    parts = [("files", (name, data)) for name, data in (files or [("r1.cfg", b"sysname r1\n")])]
    if archive is not None:
        parts = [("archive", ("snapshot.zip", archive, "application/zip"))]
    return client.post(f"/api/v1/networks/{network}/uploads", files=parts, headers=headers)


def test_upload_original_bytes_and_database_manifest(upload_app):
    client, db, app, headers = upload_app
    network = create_network(client, headers).json()["id"]
    data = "sysname 交换机\r\n".encode("gb18030") + b"\x1b[31m#\r\n"
    response = upload(client, headers, network, files=[("r1.cfg", data)])
    assert response.status_code == 201
    item = response.json()
    file = item["manifest"]["files"][0]
    assert file["path"] == "configs/r1.cfg" and file["encoding"] == "gb18030"
    root = app.state.uploads_service.storage_root
    assert (root / item["storage_key"] / file["id"]).read_bytes() == data
    assert (root / item["storage_key"]).stat().st_mode & 0o077 == 0
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM uploads")).scalar_one() == 1
    # Equal bytes and logical paths produce the same content hash, never the same upload ID.
    second = upload(client, headers, network, files=[("r1.cfg", data)]).json()
    assert second["content_hash"] == item["content_hash"] and second["id"] != item["id"]


def test_upload_owner_and_network(upload_app):
    admin, _, app, headers = upload_app
    network = create_network(admin, headers).json()["id"]
    other_network = create_network(admin, headers).json()["id"]
    add_user(admin, headers, "owner")
    add_user(admin, headers, "other")
    with TestClient(app, base_url=ORIGIN) as owner, TestClient(app, base_url=ORIGIN) as other:
        owner_headers = ready_user(owner, "owner")
        ready_user(other, "other")
        record = upload(owner, owner_headers, network).json()
        actor = app.state.auth_service.require_actor(owner.cookies.get("batfish_session"))
        outsider = app.state.auth_service.require_actor(other.cookies.get("batfish_session"))
        service = app.state.uploads_service
        with pytest.raises(ServiceError) as error:
            service.consume(outsider, UUID(network), UUID(record["id"]))
        assert error.value.code == "FORBIDDEN"
        with pytest.raises(ServiceError):
            service.consume(actor, UUID(other_network), UUID(record["id"]))
        manifest = service.consume(actor, UUID(network), UUID(record["id"]))
        assert str(manifest.upload_id) == record["id"]
        with pytest.raises(ServiceError) as error:
            service.consume(actor, UUID(network), UUID(record["id"]))
        assert error.value.code == "CONFLICT"
        record = upload(owner, owner_headers, network).json()
        administrator = app.state.auth_service.require_actor(admin.cookies.get("batfish_session"))
        assert service.consume(administrator, UUID(network), UUID(record["id"]))


def test_failed_archive_cleans_files_and_rejects_mixed_input(upload_app):
    client, db, app, headers = upload_app
    network = create_network(client, headers).json()["id"]
    response = upload(
        client, headers, network, archive=zipped([("configs/a", b"good"), ("../escape", b"bad")])
    )
    assert response.status_code == 422 and "escape" not in response.text
    response = client.post(
        f"/api/v1/networks/{network}/uploads",
        headers=headers,
        files=[("files", ("a", b"x")), ("archive", ("a.zip", b"x"))],
    )
    assert response.status_code == 422
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM uploads")).scalar_one() == 0
    assert list(app.state.uploads_service.storage_root.iterdir()) == []


def test_upload_expiration_cleanup_preserves_consumed(upload_app):
    client, db, app, headers = upload_app
    network = create_network(client, headers).json()["id"]
    record = upload(client, headers, network).json()
    kept = upload(client, headers, network).json()
    service = app.state.uploads_service
    actor = app.state.auth_service.require_actor(client.cookies.get("batfish_session"))
    service.consume(actor, UUID(network), UUID(kept["id"]))
    with db.transaction() as tx:
        tx.execute(
            text("UPDATE uploads SET expires_at=:old"),
            {"old": datetime.now(UTC) - timedelta(seconds=1)},
        )
    with pytest.raises(ServiceError):
        service.consume(actor, UUID(network), UUID(record["id"]))
    assert service.cleanup_expired() == 1
    assert not (service.storage_root / record["storage_key"]).exists()
    assert (service.storage_root / kept["storage_key"]).exists()


def test_upload_database_failure_cleans_published_directory(upload_app, monkeypatch):
    from app.modules.uploads.repository import UploadsRepository

    client, _, app, headers = upload_app
    network = create_network(client, headers).json()["id"]

    def fail(*args, **kwargs):
        raise RuntimeError("private database details")

    monkeypatch.setattr(UploadsRepository, "add", fail)
    response = upload(client, headers, network)
    assert response.status_code == 500 and "private" not in response.text
    assert list(app.state.uploads_service.storage_root.iterdir()) == []


def test_unauthenticated_upload_rejected_before_body(upload_app):
    client, _, app, headers = upload_app
    network = create_network(client, headers).json()["id"]
    with TestClient(app, base_url=ORIGIN) as anonymous:
        assert upload(anonymous, {"Origin": ORIGIN}, network).status_code == 401
    assert list(app.state.uploads_service.storage_root.iterdir()) == []


def test_concurrent_consume_only_one_wins(upload_app):
    from concurrent.futures import ThreadPoolExecutor

    client, _, app, headers = upload_app
    network = create_network(client, headers).json()["id"]
    record = upload(client, headers, network).json()
    actor = app.state.auth_service.require_actor(client.cookies.get("batfish_session"))

    def consume():
        try:
            app.state.uploads_service.consume(actor, UUID(network), UUID(record["id"]))
            return "consumed"
        except ServiceError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: consume(), range(2))) == ["CONFLICT", "consumed"]


def test_cleanup_only_old_unreferenced_directories(upload_app):
    import os
    from uuid import uuid4

    _, _, app, _ = upload_app
    service = app.state.uploads_service
    old = service.storage_root / ".tmp-interrupted"
    old.mkdir(mode=0o700)
    (old / "partial").write_bytes(b"private config")
    stale = datetime.now(UTC).timestamp() - 90000
    os.utime(old, (stale, stale))
    orphan = service.storage_root / str(uuid4())
    orphan.mkdir(mode=0o700)
    os.utime(orphan, (stale, stale))
    recent = service.storage_root / ".tmp-active"
    recent.mkdir(mode=0o700)
    external = service.storage_root.parent / "external"
    external.mkdir()
    (external / "keep").write_bytes(b"keep")
    link = service.storage_root / str(uuid4())
    link.symlink_to(external, target_is_directory=True)
    assert service.cleanup_expired() == 0
    assert not old.exists() and not orphan.exists()
    assert recent.exists() and link.is_symlink() and (external / "keep").exists()


def test_commit_failure_leaves_reconcilable_orphan(upload_app):
    from sqlalchemy import event

    client, db, app, headers = upload_app
    network = create_network(client, headers).json()["id"]

    # Flush expunges unreferenced ORM objects; inject on connection after detecting the upload INSERT.
    active = False

    def statement(connection, cursor, sql, parameters, context, executemany):
        nonlocal active
        if sql.startswith("INSERT INTO uploads"):
            active = True

    def commit(connection):
        if active:
            raise RuntimeError("uncertain commit outcome")

    event.listen(db.engine, "after_cursor_execute", statement)
    event.listen(db.engine, "commit", commit)
    try:
        response = upload(client, headers, network)
        assert response.status_code == 500
    finally:
        event.remove(db.engine, "after_cursor_execute", statement)
        event.remove(db.engine, "commit", commit)
    root = app.state.uploads_service.storage_root
    assert (
        len(list(root.iterdir())) == 1
    )  # Retained until DB outcome can be checked by TTL cleanup.
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM uploads")).scalar_one() == 0


def test_upload_limits_report_actual_settings_and_require_identity(upload_app):
    client, _, app, _ = upload_app
    response = client.get("/api/v1/upload-limits")
    assert response.status_code == 200
    limits = app.state.uploads_service.limits
    assert response.json() == {
        "max_bytes": limits.max_bytes,
        "max_expanded_bytes": limits.max_expanded_bytes,
        "max_files": limits.max_files,
    }
    with TestClient(app, base_url=ORIGIN) as anonymous:
        assert anonymous.get("/api/v1/upload-limits").status_code == 401
