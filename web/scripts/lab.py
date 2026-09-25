"""Local functional-test services and synthetic snapshots, not device emulation.

Run with the locked backend Python environment. SDK access here is test setup,
never an application-layer entry point.
"""

import argparse
import fcntl
import hashlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
BACKEND = WEB / "backend"
RUNTIME = WEB / ".runtime" / "test-lab"
CURRENT = RUNTIME / "current.json"
ENGINE_REVISION = "7d0deeeac4a09973b3876327f6aef721ee12f955"
JAR_SHA256 = "0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193"
POSTGRES_IMAGE = (
    "postgres@sha256:67f624a4ad70edba8d65c82341124fab7054b277b4f7dea4b04be6f939ce2314"
)
PROFILES = {
    "r1-r2": {
        "source": BACKEND / "tests/fixtures/small_network",
        "nodes": ["r1", "r2"],
        "start": "r1",
        "source_ip": "10.0.0.1",
        "destination": "10.0.0.2",
    },
    "cisco-four": {
        "source": BACKEND / "tests/fixtures/cisco_four",
        "nodes": ["c1", "c2", "c3", "c4"],
        "start": "c1",
        "source_ip": "10.64.0.1",
        "destination": "10.64.0.4",
    },
}


def snapshot_files(source):
    if source.is_symlink() or (source / "configs").is_symlink():
        raise ValueError("Snapshot symlink is not allowed")
    files = sorted((source / "configs").rglob("*"))
    if any(p.is_symlink() for p in files):
        raise ValueError("Snapshot symlink is not allowed")
    files = [p for p in files if p.is_file()]
    if not files:
        raise ValueError("Snapshot must contain configuration files")
    return files


def snapshot_digest(source):
    digest = hashlib.sha256()
    for path in snapshot_files(source):
        name = path.relative_to(source).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big") + name)
        digest.update(len(data).to_bytes(8, "big") + data)
    return digest.hexdigest()


def archive_snapshot(source, destination):
    files = snapshot_files(source)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(source).as_posix())
    return destination


def write_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


@contextmanager
def exclusive_run(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("A lab operation is already running") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def read_current():
    state = json.loads(CURRENT.read_text())
    if state["host"] != "127.0.0.1" or state["isolated"] is not True:
        raise ValueError("Expected an isolated local test lab")
    return state


def http_status(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def wait_until(check, processes, label, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(p.poll() is not None for p in processes):
            raise RuntimeError(f"{label}: process exited; inspect lab logs")
        try:
            if check():
                return
        except (OSError, TimeoutError):
            pass
        time.sleep(0.25)
    raise TimeoutError(f"{label}: startup timeout")


def ensure_free(port):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def serve(args):
    jar = ROOT / "bazel-bin/projects/allinone/allinone_main_deploy.jar"
    if hashlib.sha256(jar.read_bytes()).hexdigest() != JAR_SHA256:
        raise ValueError(
            "JAR differs from the verified baseline; validate and update provenance first"
        )
    java = shutil.which("java")
    if not java or not shutil.which("docker"):
        raise RuntimeError("Java and Docker are required")
    ports = (args.engine_port, args.api_port, args.database_port)
    if len(set(ports)) != 3:
        raise ValueError("Services must use three distinct ports")
    for port in ports:
        ensure_free(port)
    subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        check=True,
        stdout=subprocess.DEVNULL,
        timeout=15,
    )
    RUNTIME.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex[:12]
    run = RUNTIME / run_id
    run.mkdir(mode=0o700)
    password = secrets.token_urlsafe(24)
    password_file = run / "postgres-password"
    password_file.touch(mode=0o600)
    password_file.write_text(password)
    connection_file = run / "database.env"
    connection_file.touch(mode=0o600)
    connection_file.write_text(
        f"DATABASE_URL=postgresql://batfish_test:{password}@127.0.0.1:{args.database_port}/batfish_test\n"
    )
    state = {
        "run_id": run_id,
        "run_directory": str(run),
        "manager_pid": os.getpid(),
        "isolated": True,
        "host": "127.0.0.1",
        "engine_port": args.engine_port,
        "api_url": f"http://127.0.0.1:{args.api_port}",
        "database_port": args.database_port,
        "database_container": f"batfish-web-test-pg-{run_id}",
        "postgres_image": POSTGRES_IMAGE,
        "engine_revision": ENGINE_REVISION,
        "jar_sha256": JAR_SHA256,
        "started_at": datetime.now(UTC).isoformat(),
        "snapshots": {},
    }
    write_json(
        run / "engine-manifest.json",
        {
            "host": state["host"],
            "port": args.engine_port,
            "engine_revision": ENGINE_REVISION,
            "jar_sha256": JAR_SHA256,
        },
    )
    processes, logs = [], []
    container_id = None

    def shutdown(_signal, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, shutdown)
    try:
        container_id = subprocess.check_output(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                state["database_container"],
                "--label",
                f"batfish-web.test-run={run_id}",
                "--publish",
                f"127.0.0.1:{args.database_port}:5432",
                "--mount",
                f"type=bind,source={password_file},target=/run/secrets/postgres-password,readonly",
                "--env",
                "POSTGRES_USER=batfish_test",
                "--env",
                "POSTGRES_DB=batfish_test",
                "--env",
                "POSTGRES_PASSWORD_FILE=/run/secrets/postgres-password",
                "--mount",
                "type=tmpfs,destination=/var/lib/postgresql/data",
                POSTGRES_IMAGE,
            ],
            text=True,
            timeout=120,
        ).strip()
        for label, command in [
            (
                "engine",
                [
                    java,
                    "-Xms256m",
                    "-Xmx4g",
                    "-jar",
                    str(jar),
                    "-runclient",
                    "false",
                    "-loglevel",
                    "error",
                    "-coordinatorargs",
                    (
                        f"-workbindhost 127.0.0.1 -workv2port {args.engine_port} "
                        f"-containerslocation {run}/containers -templatedirs {ROOT}/questions"
                    ),
                ],
            ),
            (
                "api",
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.api_port),
                    "--no-access-log",
                    "--no-proxy-headers",
                ],
            ),
        ]:
            log = (run / f"{label}.log").open("w")
            logs.append(log)
            # Explicit lab values prevent accidental use of a developer's normal DB/engine.
            env = os.environ | {
                "BATFISH_HOST": "127.0.0.1",
                "BATFISH_PORT": str(args.engine_port),
                "BATFISH_API_KEY": "",
                "BATFISH_TLS": "false",
                "DATABASE_URL": connection_file.read_text().strip().split("=", 1)[1],
                "AUTH_ALLOWED_ORIGINS": json.dumps([state["api_url"]]),
                "AUTH_COOKIE_SECURE": "false",
            }
            processes.append(
                subprocess.Popen(
                    command, cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT
                )
            )
        wait_until(
            lambda: (
                http_status(f"http://127.0.0.1:{args.engine_port}/v2/version") == 200
            ),
            processes,
            "Batfish",
        )
        wait_until(
            lambda: http_status(state["api_url"] + "/api/v1/health/live") == 200,
            processes,
            "API",
        )
        wait_until(
            lambda: (
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_id,
                        "pg_isready",
                        "-U",
                        "batfish_test",
                        "-d",
                        "batfish_test",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                ).returncode
                == 0
            ),
            processes,
            "PostgreSQL",
        )
        with (run / "migration.log").open("w") as migration_log:
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=BACKEND,
                env=env,
                stdout=migration_log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=60,
            )
        state["database_migration"] = "0003"
        auth_password = secrets.token_urlsafe(24)
        auth_file = run / "auth.json"
        with open(
            auth_file, "x", opener=lambda path, flags: os.open(path, flags, 0o600)
        ) as output:
            json.dump({"username": "lab-admin", "password": auth_password}, output)
        with (run / "bootstrap.log").open("w") as bootstrap_log:
            subprocess.run(
                [sys.executable, "-m", "app.bootstrap_admin"],
                cwd=BACKEND,
                env=env
                | {
                    "BOOTSTRAP_USERNAME": "lab-admin",
                    "BOOTSTRAP_PASSWORD": auth_password,
                },
                stdout=bootstrap_log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=30,
            )
        write_json(CURRENT, state)
        write_json(run / "manifest.json", state)
        print(
            json.dumps(
                {
                    "status": "running",
                    "api": state["api_url"],
                    "batfish_port": args.engine_port,
                    "database_port": args.database_port,
                    "manifest": str(CURRENT),
                },
                indent=2,
            ),
            flush=True,
        )
        print(
            "Use seed, smoke, verify in a second terminal. Ctrl-C stops this lab only.",
            flush=True,
        )
        while all(p.poll() is None for p in processes):
            time.sleep(1)
        raise RuntimeError("A lab process exited; inspect run logs")
    except KeyboardInterrupt:
        print("Stopping test lab", flush=True)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in logs:
            log.close()
        if container_id:
            subprocess.run(
                ["docker", "stop", "--time", "5", container_id],
                stdout=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
        state["stopped_at"] = datetime.now(UTC).isoformat()
        if CURRENT.exists() and json.loads(CURRENT.read_text()).get("run_id") == run_id:
            state = json.loads(CURRENT.read_text()) | {
                "stopped_at": state["stopped_at"]
            }
            write_json(CURRENT, state)
        write_json(run / "manifest.json", state)


def seed():
    from pybatfish.client.session import Session

    state = read_current()
    if "stopped_at" in state:
        raise RuntimeError("Start the lab before seeding")
    run = Path(state["run_directory"])
    artifacts = run / "artifacts"
    artifacts.mkdir(exist_ok=True)
    for name, profile in PROFILES.items():
        digest = snapshot_digest(profile["source"])
        network = f"web-lab-{state['run_id']}-{name}"
        snapshot = f"baseline-{digest[:16]}"
        session = Session(host=state["host"], port=state["engine_port"], timeout=15)
        session.set_network(network)
        if snapshot not in session.list_snapshots():
            session.init_snapshot(
                str(profile["source"]), name=snapshot, overwrite=False
            )
        else:
            session.set_snapshot(snapshot)
        nodes = (
            session.q.nodeProperties(properties="Configuration_Format").answer().frame()
        )
        if set(nodes.Node) != set(profile["nodes"]):
            raise RuntimeError(f"{name}: unexpected parsed inventory")
        archive = archive_snapshot(profile["source"], artifacts / f"{name}.zip")
        state["snapshots"][name] = {
            **{k: v for k, v in profile.items() if k != "source"},
            "network": network,
            "snapshot": snapshot,
            "sha256": digest,
            "archive": str(archive),
        }
        print(f"Seeded {name}: {len(nodes)} nodes, {snapshot}", flush=True)
    write_json(CURRENT, state)
    write_json(run / "manifest.json", state)


def verify(smoke=False):
    state = read_current()
    if "stopped_at" in state:
        raise RuntimeError("Start the lab before verification")
    run = Path(state["run_directory"])
    evidence = run / "checks" / uuid4().hex[:12]
    evidence.mkdir(parents=True)
    env = os.environ | {
        "BATFISH_LAB_MANIFEST": str(CURRENT),
        "BATFISH_TEST_ISOLATED": "1",
        "BATFISH_TEST_HOST": state["host"],
        "BATFISH_TEST_PORT": str(state["engine_port"]),
        "BATFISH_TEST_PREFIX": "mvp01-lab",
        "BATFISH_TEST_MANIFEST": str(run / "engine-manifest.json"),
        "BATFISH_TEST_EVIDENCE": str(evidence / "sdk-baseline.json"),
    }
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        f"--junitxml={evidence}/pytest.xml",
    ]
    if smoke:
        command.extend(["-m", "smoke"])
    with (evidence / "pytest.log").open("w") as log:
        process = subprocess.Popen(
            command,
            cwd=BACKEND,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
        code = process.wait()
    write_json(
        evidence / "result.json",
        {
            "exit_code": code,
            "command": command,
            "mode": "smoke" if smoke else "full",
            "run_id": state["run_id"],
        },
    )
    print(f"Evidence: {evidence}", flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["serve", "seed", "status", "smoke", "verify"]
    )
    parser.add_argument("--engine-port", type=int, default=19996)
    parser.add_argument("--api-port", type=int, default=18000)
    parser.add_argument("--database-port", type=int, default=15439)
    args = parser.parse_args()
    if args.command == "serve":
        with exclusive_run(RUNTIME / "serve.lock"):
            serve(args)
    elif args.command == "seed":
        with exclusive_run(RUNTIME / "operations.lock"):
            seed()
    elif args.command == "status":
        state = read_current()
        print(
            json.dumps(
                {
                    "manifest": str(CURRENT),
                    "run_id": state["run_id"],
                    "api_live_status": http_status(
                        state["api_url"] + "/api/v1/health/live"
                    ),
                    "engine_status": http_status(
                        f"http://127.0.0.1:{state['engine_port']}/v2/version"
                    ),
                    "snapshots": state["snapshots"],
                },
                indent=2,
            )
        )
    else:
        with exclusive_run(RUNTIME / "operations.lock"):
            return verify(smoke=args.command == "smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
