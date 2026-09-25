"""Owned single-host deployment; secrets and engine inputs stay outside source control."""

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "web/deploy/compose.yaml"
JAR_SHA = "0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193"
REVISION = "7d0deeeac4a09973b3876327f6aef721ee12f955"


def private_write(path, value):
    with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
        stream.write(value)


def read_state(path):
    path = Path(path).resolve()
    state = json.loads((path / "deployment.json").read_text())
    if state["state_dir"] != str(path) or not re.fullmatch(
        r"bfw-[a-f0-9]{12}", state["project"]
    ):
        raise ValueError("State ownership/path mismatch")
    return state


def compose(state, *args, **kwargs):
    command = [
        "docker",
        "compose",
        "--env-file",
        str(Path(state["state_dir"]) / "compose.env"),
        "-p",
        state["project"],
        "-f",
        str(COMPOSE),
        *args,
    ]
    return subprocess.run(command, check=True, **kwargs)


def prepare(path, port=18443):
    path = Path(path).resolve()
    if path.exists():
        raise ValueError("Use a new private directory")
    if not 1024 <= port <= 65535 or any(c in str(path) for c in "\n\r$#'\""):
        raise ValueError("Invalid path or port")
    jar = ROOT / "bazel-bin/projects/allinone/allinone_main_deploy.jar"
    if hashlib.sha256(jar.read_bytes()).hexdigest() != JAR_SHA:
        raise ValueError("Engine differs from verified current-branch build")
    path.mkdir(mode=0o700, parents=True)
    state = {
        "schema_version": 1,
        "project": "bfw-" + uuid4().hex[:12],
        "state_dir": str(path),
        "port": port,
        "origin": f"https://localhost:{port}",
        "release": "mvp24-" + uuid4().hex[:12],
        "engine_revision": REVISION,
        "jar_sha256": JAR_SHA,
    }
    private_write(path / "deployment.json", json.dumps(state, indent=2) + "\n")
    write_compose_env(state)
    password = secrets.token_urlsafe(32)
    private_write(path / "db-password", password)
    private_write(
        path / "app.env",
        "\n".join(
            [
                f"DATABASE_URL=postgresql://batfish:{password}@db:5432/batfish",
                "DATA_DIR=/data",
                "BATFISH_HOST=engine",
                "BATFISH_PORT=9996",
                "BATFISH_TLS=false",
                "AUTH_COOKIE_SECURE=true",
                'AUTH_ALLOWED_ORIGINS=["' + state["origin"] + '"]',
            ]
        )
        + "\n",
    )
    engine = path / "engine"
    engine.mkdir()
    shutil.copy2(jar, engine / "batfish.jar")
    shutil.copytree(ROOT / "questions", engine / "questions")
    shutil.copy2(ROOT / "web/deploy/engine.Dockerfile", engine / "Dockerfile")
    shutil.copy2(ROOT / "web/deploy/engine-health.sh", engine / "engine-health.sh")
    (engine / "provenance.json").write_text(
        json.dumps(
            {
                "engine_revision": REVISION,
                "jar_sha256": JAR_SHA,
                "templates": {
                    str(p.relative_to(engine)): hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()
                    for p in sorted((engine / "questions").rglob("*"))
                    if p.is_file()
                },
            },
            indent=2,
        )
        + "\n"
    )
    tls = path / "tls"
    tls.mkdir(mode=0o700)
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "30",
            "-keyout",
            str(tls / "key.pem"),
            "-out",
            str(tls / "cert.pem"),
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Parent 0700 protects the key on host; file-only read-only bind permits proxy uid 101.
    (tls / "key.pem").chmod(0o444)
    return state


def write_compose_env(state):
    p = Path(state["state_dir"]) / "compose.env"
    private_write(
        p,
        "\n".join(
            [
                f"BFW_STATE={state['state_dir']}",
                f"BFW_RELEASE={state['release']}",
                f"BFW_PORT={state['port']}",
                "BFW_BIND=127.0.0.1",
            ]
        )
        + "\n",
    )


def image_identity(state):
    return {
        name: subprocess.check_output(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                f"bfw-{name}:{state['release']}",
            ],
            text=True,
        ).strip()
        for name in ["backend", "frontend", "engine"]
    }


def sql(state, query):
    return compose(
        state,
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "batfish",
        "-d",
        "batfish",
        "-Atc",
        query,
        capture_output=True,
        text=True,
    ).stdout.strip()


def volume_archive(state, folder, restore=False):
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--user",
            "0:0",
            "-v",
            f"{state['project']}_appdata:/appdata" + ("" if restore else ":ro"),
            "-v",
            f"{state['project']}_enginedata:/enginedata" + ("" if restore else ":ro"),
            "-v",
            f"{Path(folder).resolve()}:/backup" + (":ro" if restore else ""),
            f"bfw-backend:{state['release']}",
            "python",
            "-",
            "restore" if restore else "backup",
        ],
        check=True,
        input=(ROOT / "web/deploy/volume_archive.py").read_text(),
        text=True,
    )


def backup(state, folder):
    folder = Path(folder).resolve()
    if folder.exists():
        raise ValueError("Backup destination must be new")
    # Stops new writes before checking; a failed guard intentionally leaves maintenance mode active.
    compose(state, "stop", "proxy", "api", "worker")
    if (
        sql(state, "SELECT count(*) FROM jobs WHERE status IN ('queued','running')")
        != "0"
    ):
        raise RuntimeError(
            "Pending jobs: resume, drain/cancel queued work and retry backup"
        )
    if sql(state, "SELECT state FROM engine_slot") not in {"idle", ""}:
        raise RuntimeError("Engine is not idle: reconcile before backup")
    compose(state, "stop", "engine")
    folder.mkdir(mode=0o700, parents=True)
    with (folder / "database.dump").open("xb") as out:
        compose(
            state,
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            "batfish",
            "-d",
            "batfish",
            "-Fc",
            stdout=out,
        )
    volume_archive(state, folder)
    for name in ["app.env", "db-password", "deployment.json"]:
        shutil.copy2(Path(state["state_dir"]) / name, folder / name)
    shutil.copytree(Path(state["state_dir"]) / "tls", folder / "tls")
    private_write(
        folder / "images.json", json.dumps(image_identity(state), indent=2) + "\n"
    )
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in folder.iterdir()
        if p.is_file()
    }
    private_write(folder / "checksums.json", json.dumps(manifest, indent=2) + "\n")
    for p in folder.iterdir():
        if p.is_file():
            p.chmod(0o600)
    compose(state, "stop", "db")


def restore(folder, path, port):
    folder, path = Path(folder).resolve(), Path(path).resolve()
    if path.exists():
        raise ValueError("Restore never overwrites a deployment")
    if not 1024 <= port <= 65535 or any(c in str(path) for c in "\n\r$#'\""):
        raise ValueError("Invalid path or port")
    for name, digest in json.loads((folder / "checksums.json").read_text()).items():
        if (
            Path(name).name != name
            or hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest
        ):
            raise ValueError("Backup checksum mismatch")
    state = json.loads((folder / "deployment.json").read_text())
    if image_identity(state) != json.loads((folder / "images.json").read_text()):
        raise ValueError("Restore requires the exact saved image identities")
    old_origin = state["origin"]
    state.update(
        project="bfw-" + uuid4().hex[:12],
        state_dir=str(path),
        port=port,
        origin=f"https://localhost:{port}",
    )
    path.mkdir(mode=0o700, parents=True)
    private_write(path / "deployment.json", json.dumps(state, indent=2) + "\n")
    write_compose_env(state)
    private_write(
        path / "app.env",
        (folder / "app.env").read_text().replace(old_origin, state["origin"]),
    )
    shutil.copy2(folder / "db-password", path / "db-password")
    shutil.copytree(folder / "tls", path / "tls")
    compose(state, "up", "-d", "--wait", "db")
    compose(state, "run", "--rm", "--no-deps", "volume-init")
    volume_archive(state, folder, restore=True)
    with (folder / "database.dump").open("rb") as source:
        compose(
            state,
            "exec",
            "-T",
            "db",
            "pg_restore",
            "-U",
            "batfish",
            "-d",
            "batfish",
            "--exit-on-error",
            "--no-owner",
            stdin=source,
        )
    compose(state, "up", "-d", "--no-build", "--wait", "--wait-timeout", "300")
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["prepare", "build", "start", "stop", "bootstrap", "backup", "restore"],
    )
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18443)
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        state = prepare(args.state, args.port)
    elif args.action == "restore":
        if not args.backup:
            parser.error("restore requires --backup")
        state = restore(args.backup, args.state, args.port)
    else:
        state = read_state(args.state)
        if args.action == "build":
            compose(state, "build")
        elif args.action == "start":
            compose(state, "up", "-d", "--no-build", "--wait", "--wait-timeout", "300")
        elif args.action == "stop":
            compose(state, "stop")
        elif args.action == "bootstrap":
            compose(state, "exec", "api", "python", "-m", "app.bootstrap_admin")
        elif args.action == "backup":
            if not args.backup:
                parser.error("backup requires --backup")
            backup(state, args.backup)
    print(f"{args.action}: {state['project']} {state['origin']}")


if __name__ == "__main__":
    main()
