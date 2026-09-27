from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.composition import database_metadata
from app.infrastructure.storage import FileStore

pytestmark = pytest.mark.integration
BACKEND = Path(__file__).resolve().parents[1]


def migrate(database, revision="head"):
    config = Config(str(BACKEND / "alembic.ini"))
    with database.engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, revision)


def test_migration_from_empty(database):
    assert inspect(database.engine).get_table_names() == []
    migrate(database)
    tables = set(inspect(database.engine).get_table_names())
    assert tables == {
        "alembic_version",
        "users",
        "auth_sessions",
        "networks",
        "uploads",
        "snapshots",
        "jobs",
        "results",
        "audit_events",
        "idempotency_records",
        "login_attempts",
        "engine_slot",
        "worker_status",
        "engine_reconciliations",
        "comparisons",
        "business_concerns",
        "business_concern_versions",
        "check_runs",
    }
    with database.engine.connect() as conn:
        context = MigrationContext.configure(conn)
        assert compare_metadata(context, database_metadata()) == []
    migrate(database)  # repeat is safe
    config = Config(str(BACKEND / "alembic.ini"))
    with database.engine.begin() as conn:
        config.attributes["connection"] = conn
        command.downgrade(config, "base")
    assert inspect(database.engine).get_table_names() == ["alembic_version"]
    migrate(database)


def add_user(session, username="alice"):
    user_id = uuid4()
    session.execute(
        text(
            "INSERT INTO users(id, username, password_hash, role) VALUES (:id, :name, 'hash', 'member')"
        ),
        {"id": user_id, "name": username},
    )
    return user_id


def test_transaction_rollback(database, tmp_path):
    migrate(database)
    with FileStore(tmp_path / "files") as store:
        with pytest.raises(RuntimeError):
            with store.stage("result", b"data") as pending:
                with database.transaction() as session:
                    add_user(session)
                    raise RuntimeError("before publication")
                pending.publish()
        with database.transaction() as session:
            assert session.execute(text("SELECT count(*) FROM users")).scalar_one() == 0
        with pytest.raises(FileNotFoundError):
            store.read("result")
        with pytest.raises(FileExistsError):
            with store.stage("result", b"original") as pending:
                pending.publish()
            with store.stage("result", b"replacement") as pending:
                with database.transaction() as session:
                    add_user(session)
                    pending.publish()
        with database.transaction() as session:
            assert session.execute(text("SELECT count(*) FROM users")).scalar_one() == 0
        assert store.read("result") == b"original"


def test_unique_foreign_key_and_state_constraints(database):
    migrate(database)
    with database.transaction() as session:
        user = add_user(session)
        session.execute(
            text(
                "INSERT INTO networks(id, display_name, engine_name, created_by) VALUES (:id, 'Lab', 'engine-1', :user)"
            ),
            {"id": uuid4(), "user": user},
        )
    for sql, parameters in [
        (
            "INSERT INTO users(id, username, password_hash, role) VALUES (:id, 'alice', 'hash', 'member')",
            {},
        ),
        (
            "INSERT INTO networks(id, display_name, engine_name, created_by) VALUES (:id, 'Other', 'engine-1', :user)",
            {"user": user},
        ),
        (
            "INSERT INTO networks(id, display_name, engine_name, created_by) VALUES (:id, 'Other', 'engine-2', :user)",
            {"user": uuid4()},
        ),
        ("UPDATE networks SET sync_state='arbitrary'", {}),
        ("DELETE FROM users WHERE id=:user", {"user": user}),
    ]:
        with pytest.raises(IntegrityError):
            with database.transaction() as session:
                session.execute(text(sql), {"id": uuid4(), **parameters})
    with database.transaction() as session:
        session.execute(text("UPDATE networks SET deleted_at=now(), sync_state='deleted'"))
        assert session.execute(text("SELECT created_by FROM networks")).scalar_one() == user
        session.execute(
            text(
                "INSERT INTO idempotency_records(id, actor_id, route, resource_key, key, request_hash, expires_at) VALUES (:id, :user, '/jobs', 'network-1', 'key', 'hash', now()+interval '1 day')"
            ),
            {"id": uuid4(), "user": user},
        )
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.execute(
                text(
                    "INSERT INTO idempotency_records(id, actor_id, route, resource_key, key, request_hash, expires_at) VALUES (:id, :user, '/jobs', 'network-1', 'key', 'different', now()+interval '1 day')"
                ),
                {"id": uuid4(), "user": user},
            )


def test_repository_values_and_result_publication(database, tmp_path):
    from datetime import UTC, datetime

    from app.contracts.dto import AnalysisContext, ResultEnvelope
    from app.modules.results.repository import ResultsRepository
    from app.modules.users.repository import UsersRepository

    migrate(database)
    network, snapshot = uuid4(), uuid4()
    with database.transaction() as transaction:
        users = UsersRepository(transaction)
        user = users.add(username="bob", password_hash="secret-hash", role="member")
        assert "secret-hash" not in repr(user)
        assert users.get(user.id) == user
        assert users.find_by_username("bob") == user
        transaction.execute(
            text(
                "INSERT INTO networks(id, display_name, engine_name, created_by) VALUES (:id, 'Lab', 'engine-lab', :user)"
            ),
            {"id": network, "user": user.id},
        )
        transaction.execute(
            text(
                "INSERT INTO snapshots(id, network_id, engine_name, display_name, content_hash, created_by) VALUES (:id, :network, 'snapshot-1', 'Baseline', 'hash', :user)"
            ),
            {"id": snapshot, "network": network, "user": user.id},
        )
    result = ResultEnvelope(
        id=uuid4(),
        kind="table",
        schema_version="1",
        context=AnalysisContext(
            network_id=network,
            snapshot_id=snapshot,
            engine_network="engine-lab",
            engine_snapshot="snapshot-1",
            engine_version="test",
            sdk_version="test",
            schema_version="1",
        ),
        effective_parameters={},
        summary={"rows": 1},
        warnings=(),
        coverage="limited",
        truncated=False,
        created_at=datetime.now(UTC),
    )
    with FileStore(tmp_path / "files") as store:
        with pytest.raises(RuntimeError):
            with store.stage("failed-result", b"result") as pending:
                with database.transaction() as transaction:
                    ResultsRepository(transaction).add(result, storage_key="failed-result")
                    raise RuntimeError("before publish")
        with database.transaction() as transaction:
            assert ResultsRepository(transaction).get(result.id) is None
        with pytest.raises(FileNotFoundError):
            store.read("failed-result")
        with store.stage("result", b"result") as pending:
            with database.transaction() as transaction:
                ResultsRepository(transaction).add(result, storage_key="result")
                pending.publish()
        with database.transaction() as transaction:
            repository = ResultsRepository(transaction)
            assert repository.get(result.id) == result
            assert repository.storage_key(result.id) == "result"
        assert store.read("result") == b"result"
