"""Real HTTPS deployment, crash fencing, and restore checks for an owned local stack."""

import argparse
import io
import json
import secrets
import subprocess
import time
import zipfile
from pathlib import Path

import requests
from deploy import (
    ROOT,
    backup,
    compose,
    image_identity,
    private_write,
    read_state,
    restore,
    sql,
)


def wait(check, timeout=180):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            value = check()
            if value:
                return value
        except (requests.ConnectionError, subprocess.CalledProcessError):
            pass
        time.sleep(0.5)
    raise AssertionError("Deployment condition timed out")


class Client:
    def __init__(self, state):
        self.state = state
        self.http = requests.Session()
        self.http.verify = str(Path(state["state_dir"]) / "tls/cert.pem")
        self.http.headers["Origin"] = state["origin"]

    def request(self, method, path, expected=200, **kwargs):
        response = self.http.request(
            method, self.state["origin"] + "/api/v1" + path, timeout=180, **kwargs
        )
        assert response.status_code == expected, (path, response.status_code)
        return response.json() if response.content else None

    def login(self, credentials):
        info = self.request("POST", "/auth/login", json=credentials)
        cookie = next(c for c in self.http.cookies if c.name == "batfish_session")
        assert cookie.secure and "HttpOnly" in cookie._rest
        assert cookie._rest.get("SameSite", "").lower() == "lax"
        self.http.headers["X-CSRF-Token"] = info["csrf_token"]
        return info

    def job(self, identifier):
        def terminal():
            value = self.request("GET", f"/jobs/{identifier}")
            return value if value["status"] not in ["queued", "running"] else None

        return wait(terminal)

    def upload(self, network, fixture):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            folder = ROOT / "web/backend/tests/fixtures" / fixture
            for p in folder.rglob("*"):
                if p.is_file():
                    archive.writestr(str(p.relative_to(folder)), p.read_bytes())
        return self.request(
            "POST",
            f"/networks/{network}/uploads",
            expected=201,
            files={"archive": (fixture + ".zip", data.getvalue(), "application/zip")},
        )

    def initialize(self, network, fixture):
        uploaded = self.upload(network, fixture)
        return self.request(
            "POST",
            f"/networks/{network}/snapshots",
            expected=202,
            json={"display_name": fixture, "upload_id": uploaded["id"]},
        )


def validate(state):
    run = Path(state["state_dir"])
    compose(state, "up", "-d", "--no-build", "--wait", "--wait-timeout", "300")
    client = Client(state)
    wait(
        lambda: (
            client.http.get(
                state["origin"] + "/api/v1/health/ready", timeout=5
            ).status_code
            == 200
        )
    )
    credentials = {
        "username": "deployment-admin",
        "password": secrets.token_urlsafe(24),
    }
    # Bootstrap through the existing public composition function; secret travels on stdin only.
    compose(
        state,
        "exec",
        "-T",
        "api",
        "python",
        "-c",
        "import json,sys; from app.composition import initialize_administrator; "
        "from app.infrastructure.settings import Settings; v=json.load(sys.stdin); "
        "initialize_administrator(Settings(),v['username'],v['password'])",
        input=json.dumps(credentials),
        text=True,
        capture_output=True,
    )
    assert client.login(credentials)["must_change_password"]
    password = secrets.token_urlsafe(24)
    client.request(
        "POST",
        "/auth/password",
        expected=204,
        json={"current_password": credentials["password"], "new_password": password},
    )
    credentials["password"] = password
    client.login(credentials)
    private_write(run / "auth.json", json.dumps(credentials) + "\n")
    samples = []
    for fixture in ["small_network", "cisco_four"]:
        network = client.request(
            "POST",
            "/networks",
            expected=201,
            json={"display_name": "Deployment " + fixture},
        )["id"]
        started = time.monotonic()
        created = client.initialize(network, fixture)
        job = client.job(created["job_id"])
        assert job["status"] == "succeeded", job["status"]
        base = f"/networks/{network}/snapshots/{created['snapshot_id']}"
        snapshot = client.request("GET", base)
        assert snapshot["status"] in ["ready", "ready_with_warnings"]
        analysis = client.request(
            "POST", base + "/analyses/nodes", expected=202, json={}
        )
        result_job = client.job(analysis["id"])
        assert result_job["status"] == "succeeded"
        result = client.request("GET", f"/results/{result_job['result_id']}/export")
        assert len(result["data"]["rows"]) == (2 if fixture == "small_network" else 4)
        samples.append(
            {
                "fixture": fixture,
                "network": network,
                **created,
                "result_id": result_job["result_id"],
                "elapsed_seconds": time.monotonic() - started,
            }
        )
    before = client.request("GET", f"/jobs/{samples[0]['job_id']}")
    compose(state, "restart", "api")
    wait(
        lambda: (
            client.http.get(
                state["origin"] + "/api/v1/health/live", timeout=5
            ).status_code
            == 200
        )
    )
    assert client.request("GET", f"/jobs/{before['id']}") == before
    print("HTTPS bootstrap, two snapshots, persisted API restart: passed", flush=True)

    # Freeze only the owned engine, ensuring a real SDK HTTP request cannot receive its reply.
    # Kill the worker while its persisted SDK gate is busy: the outcome must remain unknown.
    network = samples[1]["network"]
    uploaded = client.upload(network, "cisco_four")
    compose(state, "pause", "engine")
    try:
        interrupted = client.request(
            "POST",
            f"/networks/{network}/snapshots",
            expected=202,
            json={"display_name": "crash-window", "upload_id": uploaded["id"]},
        )
        wait(lambda: sql(state, "SELECT state FROM engine_slot") == "busy", timeout=30)
        compose(state, "kill", "-s", "SIGKILL", "worker")
    finally:
        compose(state, "unpause", "engine")
    wait(
        lambda: (
            compose(
                state,
                "ps",
                "--format",
                "{{.Health}}",
                "engine",
                capture_output=True,
                text=True,
            ).stdout.strip()
            == "healthy"
        )
    )
    # Stale recovery uses the production default 60 s; observation repeatedly invokes recovery.
    wait(lambda: client.request("GET", "/admin/engine")["state"] == "unknown")
    compose(state, "start", "worker")
    lost = wait(
        lambda: (
            v
            if (v := client.request("GET", f"/jobs/{interrupted['job_id']}"))["status"]
            == "interrupted"
            else None
        ),
        timeout=90,
    )
    base = f"/networks/{network}/snapshots/{samples[1]['snapshot_id']}"
    queued = client.request("POST", base + "/analyses/routes", expected=202, json={})
    assert queued["status"] == "queued"
    assert client.request("GET", "/admin/engine")["state"] == "unknown"
    observation_until = time.monotonic() + 3.5
    while time.monotonic() < observation_until:
        pending = client.request("GET", f"/jobs/{queued['id']}")
        assert pending["status"] == "queued" and pending["started_at"] is None
        assert client.request("GET", "/admin/engine")["state"] == "unknown"
        time.sleep(0.5)
    client.request("POST", f"/jobs/{queued['id']}/cancel", json={})
    assert client.request("GET", "/admin/engine")["state"] == "unknown"
    compose(state, "stop", "worker")
    compose(state, "restart", "engine")
    wait(
        lambda: (
            compose(
                state,
                "exec",
                "-T",
                "engine",
                "/engine/health.sh",
                capture_output=True,
            ).returncode
            == 0
        )
    )
    wait(
        lambda: (
            compose(
                state,
                "ps",
                "--format",
                "{{.Health}}",
                "engine",
                capture_output=True,
                text=True,
            ).stdout.strip()
            == "healthy"
        )
    )
    client.request(
        "POST",
        "/admin/engine/reconcile",
        json={
            "resolution": "restarted",
            "note": "Owned deployment worker killed during pending SDK HTTP; stopped worker and restarted owned engine before reconciliation.",
        },
    )
    compose(state, "start", "worker")
    wait(
        lambda: (
            client.http.get(
                state["origin"] + "/api/v1/health/ready", timeout=5
            ).status_code
            == 200
        )
    )
    job = client.request("POST", base + "/analyses/routes", expected=202, json={})
    assert client.job(job["id"])["status"] == "succeeded"
    assert client.request("GET", f"/jobs/{lost['id']}")["status"] == "interrupted"
    print(
        "In-flight SDK worker loss, unknown fence, explicit restart/reconciliation: passed",
        flush=True,
    )

    ids = compose(state, "ps", "-aq", capture_output=True, text=True).stdout.split()
    inspected = json.loads(subprocess.check_output(["docker", "inspect", *ids]))
    for item in inspected:
        service = item["Config"]["Labels"]["com.docker.compose.service"]
        bindings = item["HostConfig"]["PortBindings"]
        assert not bindings or service == "proxy", service
        if service in ["api", "worker", "engine", "proxy"]:
            assert item["HostConfig"]["ReadonlyRootfs"]
    saved = run.parent / (run.name + "-backup")
    backup(state, saved)
    restored = restore(saved, run.parent / (run.name + "-restored"), state["port"] + 1)
    recovered = Client(restored)
    recovered.login(credentials)
    wait(
        lambda: (
            recovered.http.get(
                restored["origin"] + "/api/v1/health/ready", timeout=5
            ).status_code
            == 200
        )
    )
    for sample in samples:
        assert (
            recovered.request("GET", f"/jobs/{sample['job_id']}")["status"]
            == "succeeded"
        )
        assert (
            recovered.request("GET", f"/results/{sample['result_id']}/export")[
                "metadata"
            ]["context"]["snapshot_id"]
            == sample["snapshot_id"]
        )
        job = recovered.request(
            "POST",
            f"/networks/{sample['network']}/snapshots/{sample['snapshot_id']}/analyses/interfaces",
            expected=202,
            json={},
        )
        assert recovered.job(job["id"])["status"] == "succeeded"
    report = {
        "status": "passed",
        "state": state,
        "restored": restored,
        "samples": samples,
        "image_ids": image_identity(state),
        "checks": [
            "HTTPS and Secure cookies",
            "two topology initialization and nodes",
            "API restart persists jobs",
            "worker loss keeps unknown and interrupts job",
            "unknown blocks SDK",
            "engine restart and audited reconciliation",
            "only proxy port published",
            "read-only application images",
            "offline DB/app/engine backup",
            "new project restore and queries",
        ],
    }
    (run / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        "Offline backup and fresh-volume restore with original results and new queries: passed",
        flush=True,
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    args = parser.parse_args()
    validate(read_state(args.state))


if __name__ == "__main__":
    main()
