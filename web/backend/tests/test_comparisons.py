"""Comparison identity, direction, access and deletion references on real snapshots."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.contracts.errors import ErrorCode, ServiceError
from tests import test_networks
from tests.test_auth import ORIGIN
from tests.test_inventory import initialize
from tests.test_networks import create_network
from tests.test_snapshots import create
from tests.test_uploads import upload
from tests.test_users import add_user, ready_user

pytestmark = pytest.mark.integration
comparison_app = test_networks.network_app


def two_snapshots(comparison_app):
    state = initialize(comparison_app, "cisco_four")
    client, db, app, headers, network, baseline, actor = state
    folder = Path(__file__).parent / "fixtures/cisco_four/configs"
    files = []
    for path in sorted(folder.glob("*.cfg")):
        content = path.read_bytes()
        if path.name == "c4.cfg":
            content = content.replace(b"hostname c4", b"hostname c4\n! candidate comment")
        files.append((path.name, content))
    source = upload(client, headers, network, files=files).json()
    submitted = create(client, headers, network, source, display_name="Candidate")
    assert submitted.status_code == 202, submitted.text
    assert app.state.execution_service.run_once("worker")
    candidate = submitted.json()["snapshot_id"]
    assert client.get(f"/api/v1/networks/{network}/snapshots/{candidate}").json()["status"] in {
        "ready",
        "ready_with_warnings",
    }
    return client, db, app, headers, network, baseline, candidate, actor


def comparison_url(network):
    return f"/api/v1/networks/{network}/comparisons"


def item_url(identifier):
    return f"/api/v1/comparisons/{identifier}"


def create_comparison(client, headers, network, baseline, candidate, **extra):
    return client.post(
        comparison_url(network),
        headers=headers,
        json={
            "baseline_snapshot_id": baseline,
            "candidate_snapshot_id": candidate,
            **extra,
        },
    )


def test_comparison_direction_and_immutable_record(comparison_app):
    client, db, app, headers, network, baseline, candidate, actor = two_snapshots(comparison_app)
    created = create_comparison(
        client, headers, network, baseline, candidate, display_name="Upgrade"
    )
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["display_name"] == "Upgrade"
    assert record["network_id"] == network
    assert record["baseline_snapshot_id"] == baseline
    assert record["candidate_snapshot_id"] == candidate
    assert record["baseline_content_hash"] != record["candidate_content_hash"]
    assert record["engine_version"] and record["sdk_version"]
    assert record["coverage"] in {"complete", "limited"}
    assert client.get(item_url(record["id"])).json() == record
    listing = client.get(comparison_url(network)).json()
    assert listing["total"] == 1 and listing["items"] == [record]
    context = app.state.changes_service.context(actor, UUID(record["id"]))
    assert context.snapshot_id == UUID(candidate)
    assert context.reference_snapshot_id == UUID(baseline)
    assert context.engine_snapshot != context.engine_reference_snapshot
    with db.transaction() as tx:
        assert tx.execute(text("SELECT count(*) FROM comparisons")).scalar_one() == 1


def test_cross_network_same_snapshot_and_model_version_rejected(comparison_app):
    client, db, app, headers, network, baseline, candidate, actor = two_snapshots(comparison_app)
    assert create_comparison(client, headers, network, baseline, baseline).status_code == 422
    other_network = create_network(client, headers).json()["id"]
    assert create_comparison(client, headers, other_network, baseline, candidate).status_code == 404
    with db.transaction() as tx:
        tx.execute(
            text("UPDATE snapshots SET engine_version='other-version' WHERE id=:id"),
            {"id": UUID(candidate)},
        )
    mismatch = create_comparison(client, headers, network, baseline, candidate)
    assert mismatch.status_code == 409
    assert client.get(comparison_url(network)).json()["total"] == 0


def test_comparison_blocks_delete_and_member_cannot_delete(comparison_app):
    client, db, app, headers, network, baseline, candidate, actor = two_snapshots(comparison_app)
    created = create_comparison(client, headers, network, baseline, candidate)
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    add_user(client, headers, "comparison-reader")
    with TestClient(app, base_url=ORIGIN) as member:
        member_headers = ready_user(member, "comparison-reader")
        assert member.get(comparison_url(network)).json()["total"] == 1
        assert member.delete(item_url(identifier), headers=member_headers).status_code == 403
    for snapshot in (baseline, candidate):
        response = client.delete(
            f"/api/v1/networks/{network}/snapshots/{snapshot}", headers=headers
        )
        assert response.status_code == 409
    assert client.delete(item_url(identifier), headers=headers).status_code == 204
    assert client.get(comparison_url(network)).json()["total"] == 0
    assert client.get(item_url(identifier)).status_code == 404
    with db.transaction() as tx:
        assert tx.execute(text("SELECT deleted_at IS NOT NULL FROM comparisons")).scalar_one()
    response = client.delete(f"/api/v1/networks/{network}/snapshots/{baseline}", headers=headers)
    assert response.status_code == 202
    assert app.state.execution_service.run_once("worker")
    assert (
        client.get(f"/api/v1/networks/{network}/snapshots/{baseline}").json()["status"] == "deleted"
    )


def test_comparison_context_rejects_deleted_record(comparison_app):
    client, db, app, headers, network, baseline, candidate, actor = two_snapshots(comparison_app)
    created = create_comparison(client, headers, network, baseline, candidate)
    identifier = created.json()["id"]
    assert client.delete(item_url(identifier), headers=headers).status_code == 204
    with pytest.raises(ServiceError) as error:
        app.state.changes_service.context(actor, UUID(identifier))
    assert error.value.code == ErrorCode.NOT_FOUND


def test_comparison_create_and_snapshot_delete_are_serialized(comparison_app):
    client, db, app, headers, network, baseline, candidate, actor = two_snapshots(comparison_app)
    barrier = Barrier(2)

    def attempt(create_record):
        barrier.wait(timeout=5)
        try:
            if create_record:
                from app.modules.changes.schemas import CreateComparisonRequest

                app.state.changes_service.create(
                    actor,
                    UUID(network),
                    CreateComparisonRequest(
                        baseline_snapshot_id=UUID(baseline),
                        candidate_snapshot_id=UUID(candidate),
                    ),
                )
                return "comparison"
            app.state.lifecycle_service.delete(actor, UUID(network), UUID(baseline))
            return "deletion"
        except ServiceError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [True, False]))
    assert len(set(outcomes) & {"comparison", "deletion"}) == 1, outcomes
    assert "CONFLICT" in outcomes or "NOT_READY" in outcomes


def test_active_snapshot_job_blocks_comparison_deletion(comparison_app):
    client, db, app, headers, network, baseline, candidate, actor = two_snapshots(comparison_app)
    identifier = create_comparison(client, headers, network, baseline, candidate).json()["id"]
    pending = client.post(
        f"/api/v1/networks/{network}/snapshots/{candidate}/analyses/nodes",
        headers=headers,
        json={},
    )
    assert pending.status_code == 202
    assert client.delete(item_url(identifier), headers=headers).status_code == 409
    assert (
        client.post(f"/api/v1/jobs/{pending.json()['id']}/cancel", headers=headers).status_code
        == 200
    )
    assert client.delete(item_url(identifier), headers=headers).status_code == 204
