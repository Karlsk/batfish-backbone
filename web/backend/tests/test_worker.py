from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.contracts.errors import ServiceError
from app.infrastructure.engine import EngineGate
from app.modules.execution.service import ExecutionService, Handler
from tests import test_networks
from tests.test_jobs import prepare, submit

pytestmark = pytest.mark.integration
worker_app = test_networks.network_app


def runtime(app, db, *, handlers=None):
    return ExecutionService(
        db, app.state.auth_service, app.state.jobs_service, handlers=handlers or {}
    )


def test_two_workers_one_claim(worker_app):
    _, _, app, _, actor, context = prepare(worker_app)
    first = submit(app.state.jobs_service, actor, context)
    submit(app.state.jobs_service, actor, context)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(app.state.jobs_service.claim, ["worker-a", "worker-b"]))
    assert sum(job is not None for job in results) == 1
    assert next(job for job in results if job is not None).id == first.id


def test_worker_virtual_handler_heartbeat_and_finish(worker_app):
    _, db, app, _, actor, context = prepare(worker_app)
    job = submit(app.state.jobs_service, actor, context)
    calls = []
    execution = runtime(
        app, db, handlers={"analysis": Handler(execute=lambda current: calls.append(current.id))}
    )
    assert execution.run_once("test-worker")
    current = app.state.jobs_service.get(actor, job.id)
    assert calls == [job.id]
    assert current.status == "succeeded" and current.attempt == 1
    assert current.started_at and current.finished_at
    assert not current.cancel_allowed


def test_crash_after_remote_submission_blocks_replay(worker_app):
    _, db, app, _, actor, context = prepare(worker_app)
    job = submit(app.state.jobs_service, actor, context)
    claimed = app.state.jobs_service.claim("lost-worker")
    assert claimed.id == job.id
    # Durable state a killed worker leaves after sending remote work; no fake remote success.
    with db.transaction() as tx:
        tx.execute(
            text("UPDATE jobs SET heartbeat_at=:old WHERE id=:id"),
            {"old": datetime.now(UTC) - timedelta(seconds=61), "id": job.id},
        )
        tx.execute(
            text(
                "INSERT INTO engine_slot(id,state,owner) VALUES(1,'busy','lost-worker') ON CONFLICT(id) DO UPDATE SET state='busy',owner='lost-worker'"
            )
        )
    execution = runtime(app, db)
    assert execution.recover_stale() == 1
    current = app.state.jobs_service.get(actor, job.id)
    assert current.status == "interrupted" and current.engine_state == "unknown"
    assert current.error.code == "ENGINE_STATE_UNKNOWN"
    submit(app.state.jobs_service, actor, context)
    assert app.state.jobs_service.claim("replacement") is None


def test_disable_before_execution_never_calls_handler(worker_app):
    _, db, app, _, actor, context = prepare(worker_app)
    job = submit(app.state.jobs_service, actor, context)
    with db.transaction() as tx:
        tx.execute(text("UPDATE users SET enabled=false WHERE id=:id"), {"id": actor.user_id})
    calls = []
    execution = runtime(
        app, db, handlers={"analysis": Handler(execute=lambda job: calls.append(job.id))}
    )
    execution.run_once("worker")
    with db.transaction() as tx:
        status = tx.execute(
            text("SELECT status FROM jobs WHERE id=:id"), {"id": job.id}
        ).scalar_one()
    assert status == "failed" and calls == []


def test_retry_preserves_original(worker_app):
    _, db, app, _, actor, context = prepare(worker_app)
    old = submit(app.state.jobs_service, actor, context)

    def fail(job):
        raise ValueError("private error")

    def retry(actor, job, *, idempotency_key):
        return app.state.jobs_service.submit(
            actor, job.kind, job.context, job.requested_parameters, idempotency_key, retry_of=job.id
        )

    execution = runtime(app, db, handlers={"analysis": Handler(execute=fail, retry=retry)})
    execution.run_once("worker")
    before = app.state.jobs_service.get(actor, old.id)
    assert before.status == "failed" and "private" not in before.model_dump_json()
    key = uuid4().hex
    new = execution.retry(actor, old.id, idempotency_key=key)
    assert new.id != old.id and new.retry_of == old.id and new.status == "queued"
    assert execution.retry(actor, old.id, idempotency_key=key).id == new.id
    assert app.state.jobs_service.get(actor, old.id) == before


def test_reconciliation_admin_and_live_lock(worker_app):
    client, db, app, headers, actor, context = prepare(worker_app)
    execution = runtime(app, db)
    with pytest.raises(RuntimeError):
        with EngineGate(db).exclusive(owner="uncertain"):
            raise RuntimeError("unknown")
    response = client.post(
        "/api/v1/admin/engine/reconcile",
        json={"resolution": "confirmed_idle", "note": "Checked isolated engine is idle"},
        headers=headers,
    )
    assert response.status_code == 200 and response.json()["state"] == "idle"
    with db.transaction() as tx:
        assert (
            tx.execute(
                text("SELECT count(*) FROM audit_events WHERE action='engine.reconcile'")
            ).scalar_one()
            == 1
        )
    with EngineGate(db).exclusive(owner="active"):
        with pytest.raises(ServiceError) as error:
            execution.reconcile(
                actor,
                resolution="confirmed_idle",
                note="Not allowed while lock held",
                request_id=uuid4(),
            )
        assert error.value.code == "CONFLICT"


def test_timeout_unknown_cannot_be_cleared_by_late_sdk_return(worker_app):
    _, db, _, _, _, _ = prepare(worker_app)
    with pytest.raises(RuntimeError):
        with EngineGate(db).exclusive(owner="timed-out"):
            with db.transaction() as tx:
                EngineGate(db).mark_unknown(transaction=tx)
    assert EngineGate(db).state() == "unknown"


def _crash_process(url, schema, host, port, ready):
    import threading

    from app.composition import create_worker
    from app.infrastructure.database import Database
    from app.infrastructure.sdk import SessionFactory
    from app.infrastructure.settings import Settings

    db = Database(url, connect_args={"options": "-csearch_path=" + schema})
    settings = Settings(
        batfish_host=host, batfish_port=port, worker_heartbeat_seconds=0.2, worker_poll_seconds=0.05
    )

    def execute(job):
        with SessionFactory(db, settings).exclusive(owner=str(job.id)) as session:
            assert session.get_component_versions().get("Batfish")
            ready.send(str(job.id))
            threading.Event().wait(30)

    runner = create_worker(settings, database=db, handlers={"analysis": Handler(execute=execute)})
    runner.run()


def test_real_worker_process_crash_retains_unknown(worker_app):
    import json
    import multiprocessing
    import os
    from pathlib import Path

    _, db, app, _, actor, context = prepare(worker_app)
    job = submit(app.state.jobs_service, actor, context)
    manifest = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    with db.transaction() as tx:
        schema = tx.execute(text("SELECT current_schema()")).scalar_one()
    process_context = multiprocessing.get_context("spawn")
    receive, send = process_context.Pipe(duplex=False)
    child = process_context.Process(
        target=_crash_process,
        args=(
            db.engine.url.render_as_string(hide_password=False),
            schema,
            manifest["host"],
            manifest["engine_port"],
            send,
        ),
    )
    child.start()
    try:
        assert receive.poll(15), "Child did not complete its real SDK request"
        assert receive.recv() == str(job.id)
        child.kill()
        child.join(10)
        assert child.exitcode != 0
        with db.transaction() as tx:
            tx.execute(
                text("UPDATE jobs SET heartbeat_at=:old WHERE id=:id"),
                {"old": datetime.now(UTC) - timedelta(seconds=61), "id": job.id},
            )
        assert runtime(app, db).recover_stale() == 1
        current = app.state.jobs_service.get(actor, job.id)
        assert current.status == "interrupted" and current.engine_state == "unknown"
        assert app.state.jobs_service.claim("replacement") is None
    finally:
        if child.is_alive():
            child.kill()
            child.join(10)
        send.close()
        receive.close()


def test_budget_expiry_fences_late_success(worker_app):
    import threading

    from app.infrastructure.settings import Settings

    _, db, app, _, actor, context = prepare(worker_app)
    job = submit(app.state.jobs_service, actor, context)
    entered, finish = threading.Event(), threading.Event()
    clock = [0.0]

    def slow(job):
        with EngineGate(db).exclusive(owner=str(job.id)):
            entered.set()
            assert finish.wait(10)

    execution = ExecutionService(
        db,
        app.state.auth_service,
        app.state.jobs_service,
        handlers={"analysis": Handler(execute=slow)},
        settings=Settings(job_wait_budget_seconds=1),
        clock=lambda: clock[0],
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(execution.run_once, "worker")
        assert entered.wait(5)
        # Wait budget elapsed while handler still holds the engine lease.
        clock[0] = 2
        execution.heartbeat("worker")
        finish.set()
        running.result(timeout=5)
    current = app.state.jobs_service.get(actor, job.id)
    assert current.status == "interrupted" and EngineGate(db).state() == "unknown"
    assert execution.stop_requested


def test_reconcile_audit_failure_keeps_unknown(worker_app, monkeypatch):
    from app.modules.audit.service import AuditService

    _, db, app, _, actor, _ = prepare(worker_app)
    with db.transaction() as transaction:
        EngineGate(db).mark_unknown(transaction=transaction)

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditService, "record", fail)
    with pytest.raises(RuntimeError):
        runtime(app, db).reconcile(
            actor,
            resolution="restarted",
            note="Controlled isolated restart verified",
            request_id=uuid4(),
        )
    assert EngineGate(db).state() == "unknown"
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM engine_reconciliations")).scalar_one() == 0


def test_worker_admin_and_retry_http_permissions(worker_app):
    from fastapi.testclient import TestClient

    from tests.test_auth import ORIGIN
    from tests.test_users import add_user, ready_user

    client, db, app, headers, actor, context = prepare(worker_app)
    job = submit(app.state.jobs_service, actor, context)
    assert client.post(f"/api/v1/jobs/{job.id}/retry", headers=headers).status_code == 409
    runtime(app, db).run_once("worker")  # No registered business handler; safe failure.
    assert client.post(f"/api/v1/jobs/{job.id}/retry", headers=headers).status_code == 409
    add_user(client, headers, "member")
    with TestClient(app, base_url=ORIGIN) as member:
        member_headers = ready_user(member, "member")
        assert member.get("/api/v1/admin/engine").status_code == 403
        assert (
            member.post(
                "/api/v1/admin/engine/reconcile",
                json={"resolution": "restarted", "note": "Member cannot reconcile"},
                headers=member_headers,
            ).status_code
            == 403
        )
        assert (
            member.post(f"/api/v1/jobs/{job.id}/retry", headers=member_headers).status_code == 403
        )


def test_sdk_factory_sessions_are_scoped_to_job(worker_app):
    import json
    import os
    from pathlib import Path

    from app.infrastructure.sdk import SessionFactory
    from app.infrastructure.settings import Settings

    _, db, _, _, _, context = prepare(worker_app)
    manifest = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    factory = SessionFactory(
        db, Settings(batfish_host=manifest["host"], batfish_port=manifest["engine_port"])
    )
    with factory.for_job(context, load_questions=False) as first:
        assert first.network == context.engine_network
        first.set_network(context.engine_network + "-session-isolation")
    with factory.for_job(context, load_questions=False) as second:
        assert second is not first and second.network == context.engine_network
        assert second.snapshot is None


@pytest.mark.parametrize("raise_error", [False, True])
def test_budget_checked_on_completion_before_next_heartbeat(worker_app, raise_error):
    from app.infrastructure.settings import Settings

    _, db, app, _, actor, context = prepare(worker_app)
    job = submit(app.state.jobs_service, actor, context)
    clock = [0.0]

    def over_budget(job):
        clock[0] = 2
        if raise_error:
            raise ValueError("private delayed error")

    execution = ExecutionService(
        db,
        app.state.auth_service,
        app.state.jobs_service,
        handlers={"analysis": Handler(execute=over_budget)},
        settings=Settings(job_wait_budget_seconds=1),
        clock=lambda: clock[0],
    )
    execution.run_once("worker")
    assert app.state.jobs_service.get(actor, job.id).status == "interrupted"
    assert EngineGate(db).state() == "unknown"


def test_unknown_fence_cannot_be_overwritten_during_admission(worker_app):
    from sqlalchemy import event

    from app.infrastructure.engine import EngineBusy

    _, db, _, _, _, _ = prepare(worker_app)
    injected = False

    def after_read(connection, cursor, statement, parameters, context, executemany):
        nonlocal injected
        if not injected and statement.startswith("SELECT engine_slot.state"):
            injected = True
            with db.transaction() as transaction:
                transaction.execute(text("SET LOCAL lock_timeout='1s'"))
                EngineGate(db).mark_unknown(transaction=transaction)

    event.listen(db.engine, "after_cursor_execute", after_read)
    try:
        with pytest.raises(EngineBusy) as error:
            with EngineGate(db).exclusive(owner="admission-race"):
                pytest.fail("SDK work started after durable unknown fence")
        assert error.value.unknown
    finally:
        event.remove(db.engine, "after_cursor_execute", after_read)
    assert EngineGate(db).state() == "unknown"


def test_reconcile_requires_old_worker_to_stop(worker_app):
    from app.infrastructure.worker import worker_lease

    _, db, app, _, actor, _ = prepare(worker_app)
    with db.transaction() as transaction:
        EngineGate(db).mark_unknown(transaction=transaction)
    with worker_lease(db):
        with pytest.raises(ServiceError) as error:
            runtime(app, db).reconcile(
                actor, resolution="restarted", note="Old worker has not exited", request_id=uuid4()
            )
        assert error.value.code == "CONFLICT"
    assert EngineGate(db).state() == "unknown"


def test_budget_expired_before_handler_skips_execution(worker_app):
    from app.infrastructure.settings import Settings

    _, db, app, _, actor, context = prepare(worker_app)
    job = submit(app.state.jobs_service, actor, context)
    ticks = iter([0.0, 2.0])
    calls = []
    execution = ExecutionService(
        db,
        app.state.auth_service,
        app.state.jobs_service,
        handlers={"analysis": Handler(execute=lambda job: calls.append(job.id))},
        settings=Settings(job_wait_budget_seconds=1),
        clock=lambda: next(ticks, 2.0),
    )
    execution.run_once("worker")
    assert calls == [] and app.state.jobs_service.get(actor, job.id).status == "interrupted"
