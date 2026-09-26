"""Web integration inputs; no physical-device or Java model-fidelity oracle."""

import json
import os
import subprocess
from pathlib import Path

import httpx
import pytest
from pybatfish.client.session import Session
from pybatfish.datamodel import HeaderConstraints

pytestmark = [pytest.mark.integration, pytest.mark.lab]


@pytest.fixture(scope="module")
def lab():
    manifest = os.environ.get("BATFISH_LAB_MANIFEST")
    assert manifest, "Start and seed web/scripts/lab.py; set BATFISH_LAB_MANIFEST"
    state = json.loads(Path(manifest).read_text())
    assert state["host"] == "127.0.0.1" and state["isolated"] is True
    assert set(state["snapshots"]) == {"r1-r2", "cisco-four"}
    return state


@pytest.fixture(params=["r1-r2", "cisco-four"])
def topology(request, lab):
    profile = lab["snapshots"][request.param]
    session = Session(host=lab["host"], port=lab["engine_port"], timeout=15)
    session.set_network(profile["network"])
    session.set_snapshot(profile["snapshot"])
    return session, profile


@pytest.mark.smoke
def test_real_api_and_database_smoke(lab):
    response = httpx.get(f"{lab['api_url']}/api/v1/health/live", timeout=5)
    assert response.status_code == 200 and response.json() == {"status": "alive"}
    assert response.headers["x-request-id"]
    # No readiness producer exists in MVP-02. Do not turn it green with a fake provider.
    response = httpx.get(f"{lab['api_url']}/api/v1/health/ready", timeout=5)
    assert response.status_code == 503 and response.json()["error"]["code"] == "NOT_READY"
    result = subprocess.run(
        [
            "docker",
            "exec",
            lab["database_container"],
            "psql",
            "-U",
            "batfish_test",
            "-d",
            "batfish_test",
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "SELECT version_num FROM alembic_version",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.stdout.strip() == lab["database_migration"]


@pytest.mark.smoke
def test_seeded_inventory(topology):
    session, profile = topology
    frame = session.q.nodeProperties(properties="Configuration_Format").answer().frame()
    assert set(frame.Node) == set(profile["nodes"])
    assert len(frame) == len(profile["nodes"])


def test_configuration_initialization_and_diagnostics(topology):
    session, profile = topology
    frame = session.q.fileParseStatus().answer().frame()
    assert len(frame) == len(profile["nodes"])
    assert set(frame.Status) == {"PASSED"}
    assert session.q.parseWarning().answer().frame().empty
    assert session.q.initIssues().answer().frame().empty


def test_interface_route_and_lpm_queries(topology):
    session, profile = topology
    interfaces = session.q.interfaceProperties(properties="Primary_Address").answer().frame()
    assert not interfaces.empty
    routes = (
        session.q.routes(nodes=profile["start"], network=profile["destination"] + "/32")
        .answer()
        .frame()
    )
    assert not routes.empty
    lpm = session.q.lpmRoutes(nodes=profile["start"], ip=profile["destination"]).answer().frame()
    assert not lpm.empty and profile["destination"] + "/32" in set(lpm.Network)


def test_traceroute_query_returns_structured_paths(topology):
    session, profile = topology
    answer = session.q.traceroute(
        startLocation=profile["start"],
        headers=HeaderConstraints(
            srcIps=profile["source_ip"], dstIps=profile["destination"], ipProtocols=["ICMP"]
        ),
        maxTraces=5,
    ).answer()
    json.dumps(dict(answer), allow_nan=False)
    frame = answer.frame()
    assert not frame.empty
    for row in frame.itertuples():
        assert row.TraceCount >= len(row.Traces) >= 1
        assert any(trace.disposition == "ACCEPTED" for trace in row.Traces)
        assert all(trace.hops for trace in row.Traces)


def test_two_profiles_remain_isolated_when_interleaved(lab):
    sessions = []
    for profile in lab["snapshots"].values():
        session = Session(host=lab["host"], port=lab["engine_port"], timeout=15)
        session.set_network(profile["network"])
        session.set_snapshot(profile["snapshot"])
        sessions.append((session, profile))
    for session, profile in sessions * 2:
        nodes = session.q.nodeProperties(properties="Configuration_Format").answer().frame()
        assert set(nodes.Node) == set(profile["nodes"])


@pytest.mark.smoke
def test_real_authentication_smoke(lab):
    import secrets

    credentials_path = Path(lab["run_directory"]) / "auth.json"
    credentials = json.loads(credentials_path.read_text())
    origin = {"Origin": lab["api_url"]}
    with (
        httpx.Client(base_url=lab["api_url"], timeout=10) as first,
        httpx.Client(base_url=lab["api_url"], timeout=10) as second,
    ):
        assert first.get("/api/v1/auth/me").status_code == 401
        response = first.post("/api/v1/auth/login", json=credentials, headers=origin)
        assert response.status_code == 200
        assert first.get("/api/v1/auth/me").json()["user_id"] == response.json()["user_id"]
        assert (
            second.post("/api/v1/auth/login", json=credentials, headers=origin).status_code == 200
        )
        assert first.post("/api/v1/auth/logout", headers=origin).status_code == 403
        new_password = secrets.token_urlsafe(24)
        changed = first.post(
            "/api/v1/auth/password",
            json={"current_password": credentials["password"], "new_password": new_password},
            headers=origin | {"X-CSRF-Token": response.json()["csrf_token"]},
        )
        assert changed.status_code == 204
        credentials["password"] = new_password
        temporary = credentials_path.with_suffix(".tmp")
        with open(temporary, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
            json.dump(credentials, output)
        temporary.replace(credentials_path)
        assert second.get("/api/v1/auth/me").status_code == 401
        response = first.post("/api/v1/auth/login", json=credentials, headers=origin)
        assert response.status_code == 200 and response.json()["must_change_password"] is False
        old_cookie = first.cookies["batfish_session"]
        assert (
            first.post(
                "/api/v1/auth/logout",
                headers=origin | {"X-CSRF-Token": response.json()["csrf_token"]},
            ).status_code
            == 204
        )
        first.cookies.set("batfish_session", old_cookie)
        assert first.get("/api/v1/auth/me").status_code == 401


@pytest.mark.smoke
def test_real_user_administration_smoke(lab):
    import secrets
    from uuid import uuid4

    credentials_path = Path(lab["run_directory"]) / "auth.json"
    credentials = json.loads(credentials_path.read_text())
    origin = {"Origin": lab["api_url"]}
    with (
        httpx.Client(base_url=lab["api_url"], timeout=10) as admin,
        httpx.Client(base_url=lab["api_url"], timeout=10) as member,
    ):
        response = admin.post("/api/v1/auth/login", json=credentials, headers=origin)
        assert response.status_code == 200
        if response.json()["must_change_password"]:
            new_password = secrets.token_urlsafe(24)
            changed = admin.post(
                "/api/v1/auth/password",
                json={"current_password": credentials["password"], "new_password": new_password},
                headers=origin | {"X-CSRF-Token": response.json()["csrf_token"]},
            )
            assert changed.status_code == 204
            credentials["password"] = new_password
            credentials_path.write_text(json.dumps(credentials))
            response = admin.post("/api/v1/auth/login", json=credentials, headers=origin)
            assert response.status_code == 200
        admin_headers = origin | {"X-CSRF-Token": response.json()["csrf_token"]}
        username = "smoke-" + uuid4().hex[:12]
        temporary = secrets.token_urlsafe(24)
        created = admin.post(
            "/api/v1/users",
            json={"username": username, "temporary_password": temporary},
            headers=admin_headers,
        )
        assert created.status_code == 201 and created.json()["role"] == "member"
        user_id = created.json()["id"]
        assert admin.get("/api/v1/users").json()["total"] >= 2
        response = member.post(
            "/api/v1/auth/login", json={"username": username, "password": temporary}, headers=origin
        )
        assert response.status_code == 200
        changed_password = secrets.token_urlsafe(24)
        assert (
            member.post(
                "/api/v1/auth/password",
                json={"current_password": temporary, "new_password": changed_password},
                headers=origin | {"X-CSRF-Token": response.json()["csrf_token"]},
            ).status_code
            == 204
        )
        assert (
            member.post(
                "/api/v1/auth/login",
                json={"username": username, "password": changed_password},
                headers=origin,
            ).status_code
            == 200
        )
        assert member.get("/api/v1/users").status_code == 403
        assert (
            admin.patch(
                "/api/v1/users/" + user_id, json={"enabled": False}, headers=admin_headers
            ).status_code
            == 200
        )
        assert member.get("/api/v1/auth/me").status_code == 401
        assert (
            admin.patch(
                "/api/v1/users/" + user_id, json={"enabled": True}, headers=admin_headers
            ).status_code
            == 200
        )
        assert member.get("/api/v1/auth/me").status_code == 401
        assert (
            member.post(
                "/api/v1/auth/login",
                json={"username": username, "password": changed_password},
                headers=origin,
            ).status_code
            == 200
        )
        assert (
            admin.post(
                "/api/v1/users/" + user_id + "/reset-password",
                json={"temporary_password": temporary},
                headers=admin_headers,
            ).status_code
            == 204
        )
        assert member.get("/api/v1/auth/me").status_code == 401
        response = member.post(
            "/api/v1/auth/login", json={"username": username, "password": temporary}, headers=origin
        )
        assert response.status_code == 200 and response.json()["must_change_password"] is True
        assert (
            admin.patch(
                "/api/v1/users/" + user_id, json={"enabled": False}, headers=admin_headers
            ).status_code
            == 200
        )


def _ready_lab_admin(client, lab):
    import secrets

    path = Path(lab["run_directory"]) / "auth.json"
    credentials = json.loads(path.read_text())
    headers = {"Origin": lab["api_url"]}
    response = client.post("/api/v1/auth/login", json=credentials, headers=headers)
    assert response.status_code == 200
    if response.json()["must_change_password"]:
        password = secrets.token_urlsafe(24)
        assert (
            client.post(
                "/api/v1/auth/password",
                json={"current_password": credentials["password"], "new_password": password},
                headers=headers | {"X-CSRF-Token": response.json()["csrf_token"]},
            ).status_code
            == 204
        )
        credentials["password"] = password
        path.write_text(json.dumps(credentials))
        response = client.post("/api/v1/auth/login", json=credentials, headers=headers)
        assert response.status_code == 200
    return headers | {"X-CSRF-Token": response.json()["csrf_token"]}


@pytest.mark.smoke
def test_real_network_management_smoke(lab):
    from uuid import uuid4

    with (
        httpx.Client(base_url=lab["api_url"], timeout=15) as first,
        httpx.Client(base_url=lab["api_url"], timeout=15) as second,
    ):
        headers = _ready_lab_admin(first, lab)
        _ready_lab_admin(second, lab)
        key = uuid4().hex
        response = first.post(
            "/api/v1/networks",
            json={"display_name": "Integration lab"},
            headers=headers | {"Idempotency-Key": key},
        )
        assert response.status_code == 201
        network = response.json()
        assert network["sync_state"] == "ready"
        assert (
            first.post(
                "/api/v1/networks",
                json={"display_name": "Integration lab"},
                headers=headers | {"Idempotency-Key": key},
            ).json()["id"]
            == network["id"]
        )
        assert second.get("/api/v1/networks/" + network["id"]).json() == network
        assert (
            first.post(
                "/api/v1/networks",
                json={"display_name": "Conflicting name"},
                headers=headers | {"Idempotency-Key": key},
            ).status_code
            == 409
        )
        listing = first.get("/api/v1/networks").json()
        assert listing["total"] >= 1
        assert not {item["engine_name"] for item in listing["items"]} & {
            item["network"] for item in lab["snapshots"].values()
        }
        sdk = Session(host=lab["host"], port=lab["engine_port"], timeout=10, load_questions=False)
        assert network["engine_name"] in sdk.list_networks()


@pytest.mark.smoke
@pytest.mark.parametrize(
    "fixture_name,mode", [("small_network", "files"), ("cisco_four", "archive")]
)
def test_real_configuration_upload_smoke(lab, fixture_name, mode):
    import hashlib
    import io
    import zipfile

    root = Path(__file__).resolve().parents[1] / "fixtures" / fixture_name
    originals = {
        f"configs/{file.name}": file.read_bytes() for file in sorted((root / "configs").iterdir())
    }
    with httpx.Client(base_url=lab["api_url"], timeout=20) as client:
        headers = _ready_lab_admin(client, lab)
        response = client.post(
            "/api/v1/networks", json={"display_name": "Upload " + fixture_name}, headers=headers
        )
        assert response.status_code == 201
        network = response.json()["id"]
        if mode == "files":
            parts = [("files", (name.split("/")[-1], data)) for name, data in originals.items()]
        else:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, data in originals.items():
                    archive.writestr("snapshot/" + name, data)
            parts = [("archive", ("snapshot.zip", stream.getvalue(), "application/zip"))]
        response = client.post(f"/api/v1/networks/{network}/uploads", files=parts, headers=headers)
        assert response.status_code == 201
        record = response.json()
        assert len(record["manifest"]["files"]) == len(originals)
        for entry in record["manifest"]["files"]:
            assert entry["sha256"] == hashlib.sha256(originals[entry["path"]]).hexdigest()
            assert (
                Path(lab["run_directory"])
                / "data"
                / "uploads"
                / record["storage_key"]
                / entry["id"]
            ).read_bytes() == originals[entry["path"]]


@pytest.mark.smoke
def test_real_job_metadata_smoke(lab):
    from uuid import uuid4

    from app.composition import create_app
    from app.contracts.dto import ExecutionContext
    from app.infrastructure.database import Database
    from app.infrastructure.settings import Settings

    with httpx.Client(base_url=lab["api_url"], timeout=20) as client:
        headers = _ready_lab_admin(client, lab)
        network = client.post(
            "/api/v1/networks", json={"display_name": "Job metadata smoke"}, headers=headers
        )
        assert network.status_code == 201
        network = network.json()
        secret = Path(lab["run_directory"]) / "database.env"
        db = Database(secret.read_text().strip().removeprefix("DATABASE_URL="))
        try:
            app = create_app(Settings(), database=db)
            actor = app.state.auth_service.require_actor(client.cookies.get("batfish_session"))
            context = ExecutionContext(
                network_id=network["id"],
                engine_network=network["engine_name"],
                engine_version="0.36.0",
                sdk_version="2026.9.17.3748",
                schema_version="1",
            )
            # There is no generic submit HTTP endpoint; real submission currently uses its service.
            job = app.state.jobs_service.submit(
                actor, "analysis", context, {"operation": "mvp08-metadata-smoke"}, uuid4().hex
            )
            response = client.get("/api/v1/jobs/" + str(job.id))
            assert response.status_code == 200 and response.json()["status"] == "queued"
            assert (
                client.get("/api/v1/jobs", params={"network_id": network["id"]}).json()["total"]
                == 1
            )
            cancelled = client.post("/api/v1/jobs/" + str(job.id) + "/cancel", headers=headers)
            assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
            assert not cancelled.json()["cancel_allowed"] and cancelled.json()["finished_at"]
            assert (
                client.post("/api/v1/jobs/" + str(job.id) + "/cancel", headers=headers).status_code
                == 409
            )
        finally:
            db.close()


@pytest.mark.smoke
def test_real_worker_lifecycle_and_readiness(lab):
    import sys
    import time

    run = Path(lab["run_directory"])
    assert (run / "worker-paused.ack").exists(), (
        "Lab manager must pause its worker before serial SDK tests"
    )
    env = os.environ | {
        "DATABASE_URL": (run / "database.env").read_text().strip().removeprefix("DATABASE_URL="),
        "BATFISH_HOST": lab["host"],
        "BATFISH_PORT": str(lab["engine_port"]),
        "BATFISH_API_KEY": "",
        "BATFISH_TLS": "false",
        "DATA_DIR": str(run / "data"),
        "WORKER_HEARTBEAT_SECONDS": "0.2",
        "WORKER_POLL_SECONDS": "0.1",
        "ENGINE_PROBE_SECONDS": "1",
    }
    with (run / "worker-smoke.log").open("a") as log:
        worker = subprocess.Popen(
            [sys.executable, "-m", "app.worker"],
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            while httpx.get(lab["api_url"] + "/api/v1/health/ready").status_code != 200:
                assert worker.poll() is None and time.monotonic() < deadline
                time.sleep(0.1)
            with httpx.Client(base_url=lab["api_url"], timeout=10) as client:
                headers = _ready_lab_admin(client, lab)
                assert client.get("/api/v1/admin/engine").json()["state"] in {"idle", "busy"}
                # A healthy idle engine has nothing to reconcile.
                assert (
                    client.post(
                        "/api/v1/admin/engine/reconcile",
                        json={"resolution": "confirmed_idle", "note": "No unknown work"},
                        headers=headers,
                    ).status_code
                    == 409
                )
            second = subprocess.run(
                [sys.executable, "-m", "app.worker"],
                cwd=Path(__file__).resolve().parents[2],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=10,
            )
            assert second.returncode != 0
        finally:
            worker.terminate()
            worker.wait(timeout=15)
        assert httpx.get(lab["api_url"] + "/api/v1/health/ready").status_code == 503


@pytest.mark.smoke
@pytest.mark.parametrize("fixture_name,expected_nodes", [("small_network", 2), ("cisco_four", 4)])
def test_real_snapshot_worker_smoke(lab, fixture_name, expected_nodes):
    import sys
    import time

    from tests.test_upload_archives import zipped

    run = Path(lab["run_directory"])
    assert (run / "worker-paused.ack").exists()
    with httpx.Client(base_url=lab["api_url"], timeout=20) as client:
        headers = _ready_lab_admin(client, lab)
        network_response = client.post(
            "/api/v1/networks", json={"display_name": "Snapshot worker smoke"}, headers=headers
        )
        assert network_response.status_code == 201
        network = network_response.json()["id"]
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / fixture_name / "configs"
        uploaded = client.post(
            f"/api/v1/networks/{network}/uploads",
            headers=headers,
            files=[
                (
                    "archive",
                    (
                        "snapshot.zip",
                        zipped(
                            [
                                ("configs/" + p.name, p.read_bytes())
                                for p in sorted(fixture.iterdir())
                            ]
                        ),
                        "application/zip",
                    ),
                )
            ],
        )
        assert uploaded.status_code == 201
        body = {
            "display_name": fixture_name,
            "upload_id": uploaded.json()["id"],
            "options": {"parse_reuse": True},
        }
        response = client.post(f"/api/v1/networks/{network}/snapshots", json=body, headers=headers)
        assert response.status_code == 202
        created = response.json()
        assert client.get("/api/v1/jobs/" + created["job_id"]).json()["status"] == "queued"
        env = os.environ | {
            "DATABASE_URL": (run / "database.env")
            .read_text()
            .strip()
            .removeprefix("DATABASE_URL="),
            "BATFISH_HOST": lab["host"],
            "BATFISH_PORT": str(lab["engine_port"]),
            "BATFISH_API_KEY": "",
            "BATFISH_TLS": "false",
            "DATA_DIR": str(run / "data"),
            "WORKER_HEARTBEAT_SECONDS": "0.2",
            "WORKER_POLL_SECONDS": "0.1",
            "ENGINE_PROBE_SECONDS": "30",
        }
        with (run / "snapshot-worker-smoke.log").open("a") as log:
            worker = subprocess.Popen(
                [sys.executable, "-m", "app.worker"],
                cwd=Path(__file__).resolve().parents[2],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 45
                while True:
                    job = client.get("/api/v1/jobs/" + created["job_id"]).json()
                    if job["status"] not in {"queued", "running"}:
                        break
                    assert worker.poll() is None and time.monotonic() < deadline
                    time.sleep(0.1)
                assert job["status"] == "succeeded", job
                detail = client.get(
                    f"/api/v1/networks/{network}/snapshots/{created['snapshot_id']}"
                ).json()
                assert detail["status"] == "ready"
                assert detail["quality_summary"]["node_count"] == expected_nodes
                assert detail["engine_version"] == "0.36.0"
                assert detail["sdk_version"] == "2026.9.17.3748"
                assert "manifest" not in detail and "diagnostics" not in detail
                base = f"/api/v1/networks/{network}/snapshots/{created['snapshot_id']}"
                diagnostics = client.get(base + "/diagnostics").json()
                assert diagnostics["total"] == expected_nodes
                entries = client.get(base + "/files").json()["items"]
                assert len(entries) == expected_nodes
                originals = {p.name: p.read_bytes() for p in fixture.iterdir()}
                for entry in entries:
                    page = client.get(base + "/files/" + entry["id"], params={"limit": 200}).json()
                    expected = originals[entry["path"].split("/")[-1]].decode("utf-8").splitlines()
                    assert [line["text"] for line in page["lines"]] == expected
                    assert [line["number"] for line in page["lines"]] == list(
                        range(1, len(expected) + 1)
                    )
                if fixture_name == "small_network":
                    assert detail["quality_summary"]["coverage"] == "limited"
                    assert detail["quality_summary"]["model_limits"]
                for operation in (
                    "nodes",
                    "interfaces",
                    "routes",
                    "lpm-routes",
                    "traceroute",
                    "topology",
                    "bgp-sessions",
                ):
                    body = (
                        {"ip": "10.0.0.2" if fixture_name == "small_network" else "10.64.0.4"}
                        if operation == "lpm-routes"
                        else {}
                    )
                    if operation == "traceroute":
                        body = {
                            "start_location": "r1" if fixture_name == "small_network" else "c1",
                            "destination_ip": "10.0.0.2"
                            if fixture_name == "small_network"
                            else "10.64.0.4",
                        }
                    submitted = client.post(
                        base + "/analyses/" + operation, json=body, headers=headers
                    )
                    assert submitted.status_code == 202, submitted.text
                    deadline = time.monotonic() + 45
                    while True:
                        finished = client.get("/api/v1/jobs/" + submitted.json()["id"]).json()
                        if finished["status"] not in {"queued", "running"}:
                            break
                        assert worker.poll() is None and time.monotonic() < deadline
                        time.sleep(0.1)
                    assert finished["status"] == "succeeded", finished
                    result_url = "/api/v1/results/" + finished["result_id"]
                    assert client.get(result_url).status_code == 200
                    if operation == "topology":
                        graph = client.get(result_url + "/graph").json()
                        assert len(graph["nodes"]) == expected_nodes and graph["edges"]
                        assert graph["source"] == "layer3Edges" and not graph["truncated"]
                        continue
                    if operation == "traceroute":
                        flows = client.get(result_url + "/flows").json()["items"]
                        assert flows
                        for flow in flows:
                            paths = client.get(
                                result_url + "/flows/" + flow["flow_id"] + "/traces"
                            ).json()
                            assert paths["items"] and paths["items"][0]["hops"][0]["steps"]
                            assert (
                                flow["trace_count"]
                                >= flow["returned_trace_count"]
                                == len(paths["items"])
                            )
                        continue
                    rows = client.get(result_url + "/rows").json()
                    if operation == "bgp-sessions":
                        assert rows["total"] == 0
                        assert any(
                            "model" in warning.lower()
                            for warning in client.get(result_url).json()["warnings"]
                        )
                    else:
                        assert (
                            rows["total"] == expected_nodes
                            if operation == "nodes"
                            else rows["total"] >= expected_nodes
                        )
                capabilities = client.get("/api/v1/capabilities")
                assert capabilities.status_code == 200
                assert {item["id"] for item in capabilities.json() if item["enabled"]} == {
                    "nodes",
                    "interfaces",
                    "routes",
                    "lpm-routes",
                    "traceroute",
                    "topology",
                    "bgp-sessions",
                    "test-filters",
                    "resolve-filters",
                    "search-filters",
                    "filter-line-reachability",
                }
            finally:
                worker.terminate()
                worker.wait(timeout=15)


@pytest.mark.smoke
def test_real_config_and_route_diff_worker_smoke(lab):
    """The running API and separate worker publish both directional comparisons."""
    import time

    run = Path(lab["run_directory"])
    assert (run / "worker-paused.ack").exists()
    fixture = Path(__file__).resolve().parents[1] / "fixtures/cisco_four/configs"
    originals = [
        (
            path.name,
            path.read_bytes().replace(b"end", b"ip route 198.51.100.0 255.255.255.0 Null0\nend")
            if path.name == "c1.cfg"
            else path.read_bytes(),
        )
        for path in sorted(fixture.iterdir())
    ]
    candidate_files = [
        (
            name,
            content.replace(
                b"ip route 198.51.100.0 255.255.255.0 Null0",
                b"ip route 203.0.113.0 255.255.255.0 Null0",
            )
            if name == "c1.cfg"
            else content,
        )
        for name, content in originals
    ]
    candidate_files = [
        (
            name,
            content.replace(
                b"end",
                b"ip access-list extended BLOCK-TO-C4\n deny ip any host 10.64.0.4\n"
                b" permit ip any any\n!\ninterface GigabitEthernet0/0\n"
                b" ip access-group BLOCK-TO-C4 out\n!\ninterface GigabitEthernet0/1\n"
                b" ip access-group BLOCK-TO-C4 out\n!\nend",
            )
            if name == "c1.cfg"
            else content,
        )
        for name, content in candidate_files
    ]
    env = os.environ | {
        "DATABASE_URL": (run / "database.env").read_text().strip().removeprefix("DATABASE_URL="),
        "BATFISH_HOST": lab["host"],
        "BATFISH_PORT": str(lab["engine_port"]),
        "BATFISH_API_KEY": "",
        "BATFISH_TLS": "false",
        "DATA_DIR": str(run / "data"),
        "WORKER_HEARTBEAT_SECONDS": "0.2",
        "WORKER_POLL_SECONDS": "0.1",
        "ENGINE_PROBE_SECONDS": "30",
    }
    with httpx.Client(base_url=lab["api_url"], timeout=30) as client:
        headers = _ready_lab_admin(client, lab)
        response = client.post(
            "/api/v1/networks", json={"display_name": "Config diff smoke"}, headers=headers
        )
        assert response.status_code == 201, response.text
        network = response.json()["id"]

        def create_snapshot(label, files):
            uploaded = client.post(
                f"/api/v1/networks/{network}/uploads",
                headers=headers,
                files=[("files", (name, content)) for name, content in files],
            )
            assert uploaded.status_code == 201, uploaded.text
            created = client.post(
                f"/api/v1/networks/{network}/snapshots",
                json={"display_name": label, "upload_id": uploaded.json()["id"]},
                headers=headers,
            )
            assert created.status_code == 202, created.text
            return created.json()

        baseline = create_snapshot("Baseline", originals)
        candidate = create_snapshot("Candidate", candidate_files)
        with (run / "config-diff-worker-smoke.log").open("a") as log:
            worker = subprocess.Popen(
                [os.sys.executable, "-m", "app.worker"],
                cwd=Path(__file__).resolve().parents[2],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:

                def finished(job_id):
                    deadline = time.monotonic() + 90
                    while True:
                        job = client.get(f"/api/v1/jobs/{job_id}").json()
                        if job["status"] not in {"queued", "running"}:
                            return job
                        assert worker.poll() is None and time.monotonic() < deadline
                        time.sleep(0.1)

                for item in (baseline, candidate):
                    job = finished(item["job_id"])
                    assert job["status"] == "succeeded", job
                comparison = client.post(
                    f"/api/v1/networks/{network}/comparisons",
                    headers=headers,
                    json={
                        "baseline_snapshot_id": baseline["snapshot_id"],
                        "candidate_snapshot_id": candidate["snapshot_id"],
                    },
                )
                assert comparison.status_code == 201, comparison.text
                submitted = client.post(
                    f"/api/v1/comparisons/{comparison.json()['id']}/analyses/config-diff",
                    json={},
                    headers=headers,
                )
                assert submitted.status_code == 202, submitted.text
                job = finished(submitted.json()["id"])
                assert job["status"] == "succeeded", job
                result = client.get(f"/api/v1/results/{job['result_id']}").json()
                assert result["kind"] == "diff"
                assert result["context"]["snapshot_id"] == candidate["snapshot_id"]
                assert result["context"]["reference_snapshot_id"] == baseline["snapshot_id"]
                files = client.get(f"/api/v1/results/{job['result_id']}/diff/files").json()
                assert files["total"] == 1
                assert files["items"][0]["path"] == "configs/c1.cfg"
                assert files["items"][0]["change"] == "changed"
                submitted = client.post(
                    f"/api/v1/comparisons/{comparison.json()['id']}/analyses/routes-diff",
                    json={
                        "nodes": {"mode": "literal", "values": ["c1"]},
                        "options": {"protocols": ["static"]},
                    },
                    headers=headers,
                )
                assert submitted.status_code == 202, submitted.text
                job = finished(submitted.json()["id"])
                assert job["status"] == "succeeded", job
                result = client.get(f"/api/v1/results/{job['result_id']}").json()
                assert result["kind"] == "table"
                assert result["context"]["snapshot_id"] == candidate["snapshot_id"]
                assert result["context"]["reference_snapshot_id"] == baseline["snapshot_id"]
                rows = client.get(f"/api/v1/results/{job['result_id']}/rows").json()["rows"]
                assert {row["Network"]: row["Change"] for row in rows} == {
                    "198.51.100.0/24": "removed",
                    "203.0.113.0/24": "added",
                }
                submitted = client.post(
                    f"/api/v1/comparisons/{comparison.json()['id']}/analyses/reachability-diff",
                    json={
                        "destination_ips": "10.64.0.4",
                        "start_location": "c1",
                        "options": {"source_ips": "10.64.0.1", "max_traces": 20},
                    },
                    headers=headers,
                )
                assert submitted.status_code == 202, submitted.text
                job = finished(submitted.json()["id"])
                assert job["status"] == "succeeded", job
                result = client.get(f"/api/v1/results/{job['result_id']}").json()
                assert result["summary"]["count_scope"] == "sdk_witness_rows_not_all_business_flows"
                rows = client.get(f"/api/v1/results/{job['result_id']}/rows").json()["rows"]
                assert len(rows) == 1 and rows[0]["Change"] == "removed"
                assert rows[0]["Flow"]["dstIp"] == "10.64.0.4"
            finally:
                worker.terminate()
                worker.wait(timeout=15)
