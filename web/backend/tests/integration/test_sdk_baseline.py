"""MVP-01: public SDK contracts against an explicitly isolated, real engine.

See web/docs/sdk-compatibility.md for environment variables and reproduction.
No API/controller implementation and no private SDK calls live in this suite.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
import json
import os
import platform
import re
import shutil
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from uuid import UUID, uuid4

import pytest
from pybatfish.client.session import Session
from pybatfish.datamodel import HeaderConstraints
from pybatfish.exception import BatfishException, QuestionValidationException
from requests.exceptions import HTTPError

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "small_network"
REQUIRED = {
    "nodeProperties", "interfaceProperties", "routes", "lpmRoutes", "traceroute",
    "fileParseStatus", "parseWarning", "initIssues", "viConversionWarning",
}


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    required = (
        "BATFISH_TEST_HOST", "BATFISH_TEST_PORT", "BATFISH_TEST_PREFIX",
        "BATFISH_TEST_MANIFEST", "BATFISH_TEST_EVIDENCE",
    )
    missing = [key for key in required if not os.environ.get(key)]
    if missing or os.environ.get("BATFISH_TEST_ISOLATED") != "1":
        pytest.fail("Explicit isolated engine configuration required: " + ", ".join(missing))
    manifest = json.loads(Path(os.environ["BATFISH_TEST_MANIFEST"]).read_text())
    host = os.environ["BATFISH_TEST_HOST"]
    port = int(os.environ["BATFISH_TEST_PORT"])
    prefix = os.environ["BATFISH_TEST_PREFIX"]
    assert host in {"127.0.0.1", "localhost", "::1"}, "Use a local isolated test engine"
    assert re.fullmatch(r"mvp01-[a-zA-Z0-9-]+", prefix), "Use an explicit mvp01- prefix"
    assert (manifest["host"], manifest["port"]) == (host, port)
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["engine_revision"])
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["jar_sha256"])
    output = Path(os.environ["BATFISH_TEST_EVIDENCE"])
    assert not output.exists(), "Choose a new evidence file for every run"
    assert importlib.metadata.version("pybatfish") == "2026.9.17.3748"

    evidence = {
        "engine_revision": manifest["engine_revision"],
        "jar_sha256": manifest["jar_sha256"],
        "python": platform.python_version(),
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "fixture_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((FIXTURE / "configs").glob("*.cfg"))
        },
        "observations": {},
        "answers": {},
    }
    context = {
        "host": host, "port": port, "prefix": prefix + "-" + uuid4().hex[:12],
        "evidence": evidence, "temp": tmp_path_factory.mktemp("sdk-baseline"),
    }
    try:
        context["a"] = Session(host=host, port=port, timeout=10)
        context["b"] = Session(host=host, port=port, timeout=10)
        yield context
    finally:
        # Partial observations are useful on failure; pytest XML decides pass/fail.
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False) + "\n")


def answer(context, session, question_id, snapshot, **params):
    started = time.monotonic()
    effective_snapshot = session.get_snapshot(snapshot)
    question = getattr(session.q, question_id)(**params)
    result = question.answer(snapshot=snapshot)
    assert result["status"] == "SUCCESS"
    frame = result.frame()
    # The raw dictionary preserves nested JSON; the DataFrame holds SDK objects.
    json.dumps(result.dict(), allow_nan=False)
    sequence = len(context["evidence"]["answers"]) + 1
    context["evidence"]["answers"][f"{sequence:03}/{session.network}/{effective_snapshot}/{question_id}"] = {
        "network": session.network, "snapshot": effective_snapshot,
        "question": question_id, "explicit_snapshot": snapshot is not None,
        "seconds": round(time.monotonic() - started, 4),
        "parameters": json.loads(question.json())["instance"].get("variables", {}),
        "column_schema": result["answerElements"][0]["metadata"]["columnMetadata"],
        "row_count": len(frame),
        "cell_types": {c: sorted({type(v).__name__ for v in frame[c]}) for c in frame.columns},
        "rows": result["answerElements"][0].get("rows", []),
    }
    return frame


@pytest.fixture(scope="module")
def snapshots(baseline):
    a, b = baseline["a"], baseline["b"]
    alternate = baseline["temp"] / "alternate"
    shutil.copytree(FIXTURE, alternate)
    for config in (alternate / "configs").glob("*.cfg"):
        config.write_text(config.read_text().replace("10.0.0.2", "10.0.0.22"))
    identities = []
    for session, suffix, source in ((a, "a", FIXTURE), (b, "b", alternate)):
        network = baseline["prefix"] + "-" + suffix
        snapshot = "snapshot-" + suffix
        assert network not in session.list_networks()
        assert session.set_network(network) == network
        assert network in session.list_networks()
        assert session.set_network(network) == network  # Existing selection is idempotent.
        started = time.monotonic()
        assert session.init_snapshot(str(source), name=snapshot, overwrite=False) == snapshot
        assert snapshot in session.list_snapshots()
        assert session.get_snapshot() == snapshot
        identities.append({"display_label": "baseline", "network": network, "snapshot": snapshot,
                           "init_seconds": round(time.monotonic() - started, 4)})
    baseline["evidence"]["observations"]["identities"] = identities
    return baseline


def test_versions_templates_and_public_methods(baseline):
    session = baseline["a"]
    versions = session.get_component_versions()
    assert versions.get("Batfish") and "api_version" in versions
    loaded = {q["name"] for q in session.q.list()}
    local = {p.stem: p for area in ("stable", "experimental")
             for p in (ROOT / "questions" / area).glob("*.json")}
    assert REQUIRED <= loaded
    assert set(local) == loaded, "Runtime templates must match this engine checkout"
    templates = {}
    for name, path in sorted(local.items()):
        remote = getattr(session.q, name).template
        local_template = json.loads(path.read_text())
        # The SDK normalizes variable descriptions/type whitespace when loading.
        # Preserve every semantic field while applying that documented source behavior.
        for variable in local_template["instance"].get("variables", {}).values():
            variable["type"] = variable["type"].strip()
            description = variable["description"].strip()
            variable["description"] = description if description.endswith(".") else description + "."
        assert remote == local_template, name
        templates[name] = {"source": path.parent.name,
                           "variables": remote["instance"].get("variables", {})}
    baseline["evidence"].update({"engine_versions": versions, "templates": templates})
    baseline["evidence"]["public_session_signatures"] = {
        name: str(inspect.signature(method)) for name, method in inspect.getmembers(Session)
        if not name.startswith("_") and callable(method)
    }


def test_minimal_questions_match_expected(snapshots):
    session = snapshots["a"]
    nodes = answer(snapshots, session, "nodeProperties", "snapshot-a", properties="Configuration_Format")
    assert set(nodes.Node) == {"r1", "r2"}
    assert set(nodes.Configuration_Format) == {"HUAWEI_VRP", "H3C_COMWARE"}
    interfaces = answer(snapshots, session, "interfaceProperties", "snapshot-a", properties="Primary_Address")
    assert {"10.0.0.1/32", "10.0.0.2/32", "192.0.2.1/30", "192.0.2.2/30"} <= set(interfaces.Primary_Address)
    routes = answer(snapshots, session, "routes", "snapshot-a", nodes="r1", network="10.0.0.2/32")
    assert len(routes) == 1 and set(routes.Protocol) == {"static"}
    lpm = answer(snapshots, session, "lpmRoutes", "snapshot-a", nodes="r1", ip="10.0.0.2")
    assert len(lpm) == 1 and set(lpm.Network) == {"10.0.0.2/32"}
    traces = answer(snapshots, session, "traceroute", "snapshot-a", startLocation="r1",
                    headers=HeaderConstraints(srcIps="10.0.0.1", dstIps="10.0.0.2", ipProtocols=["ICMP"]))
    assert len(traces) == 1
    assert traces.iloc[0].TraceCount == 1
    trace = traces.iloc[0].Traces[0]
    assert trace.disposition == "ACCEPTED"
    assert [hop.node for hop in trace.hops] == ["r1", "r2"]


def test_session_context_isolation(snapshots):
    a, b = snapshots["a"], snapshots["b"]
    assert a is not b and a.network != b.network
    a.set_snapshot("snapshot-a")
    b.set_snapshot("snapshot-b")
    for session, snapshot, address, absent in (
        (a, "snapshot-a", "10.0.0.2/32", "10.0.0.22/32"),
        (b, "snapshot-b", "10.0.0.22/32", "10.0.0.2/32"),
        (a, "snapshot-a", "10.0.0.2/32", "10.0.0.22/32"),
        (b, "snapshot-b", "10.0.0.22/32", "10.0.0.2/32"),
    ):
        assert session.get_snapshot() == snapshot
        # Omitting the override exercises each Session's own mutable context.
        frame = answer(snapshots, session, "interfaceProperties", None, nodes="r2", properties="Primary_Address")
        assert address in set(frame.Primary_Address)
        assert absent not in set(frame.Primary_Address)
    snapshots["evidence"]["observations"]["session_isolation"] = "A/B/A/B: addresses stay in their network/snapshot"


def test_initialization_diagnostics_and_no_overwrite(snapshots, caplog):
    session = snapshots["a"]
    status = answer(snapshots, session, "fileParseStatus", "snapshot-a")
    assert len(status) == 2 and set(status.Status) == {"PASSED"}
    assert answer(snapshots, session, "parseWarning", "snapshot-a").empty
    assert answer(snapshots, session, "viConversionWarning", "snapshot-a").empty
    assert answer(snapshots, session, "initIssues", "snapshot-a").empty
    with pytest.raises(ValueError, match="already exists"):
        session.init_snapshot(str(FIXTURE), name="snapshot-a", overwrite=False)
    warning_source = snapshots["temp"] / "warning"
    shutil.copytree(FIXTURE, warning_source)
    config = warning_source / "configs" / "r1.cfg"
    config.write_text(config.read_text().replace("return", "mvp01-unsupported-command\nreturn"))
    assert session.init_snapshot(str(warning_source), name="warning", overwrite=False) == "warning"
    warnings = answer(snapshots, session, "parseWarning", "warning")
    assert not warnings.empty
    assert warnings.to_string().find("mvp01-unsupported-command") >= 0
    assert not answer(snapshots, session, "initIssues", "warning").empty
    warning_status = answer(snapshots, session, "fileParseStatus", "warning")
    assert "PARTIALLY_UNRECOGNIZED" in set(warning_status.Status)
    snapshots["evidence"]["observations"]["initialization"] = {
        "return_type": "str", "warning_snapshot_return": "warning",
        "duplicate_overwrite_false": "ValueError", "warning_logged": bool(caplog.records),
        "snapshot_metadata": session.list_snapshots(verbose=True),
    }


def test_unsupported_or_missing_question(snapshots):
    session = snapshots["a"]
    assert "mvp01MissingQuestion" not in {q["name"] for q in session.q.list()}
    with pytest.raises(AttributeError):
        getattr(session.q, "mvp01MissingQuestion")
    with pytest.raises(QuestionValidationException):
        session.q.routes(mvp01UnknownOption=True)
    with pytest.raises((HTTPError, BatfishException)) as error:
        session.q.nodeProperties().answer(snapshot="mvp01-missing-snapshot")
    snapshots["evidence"]["observations"]["unsupported"] = {
        "missing_question": "AttributeError", "unknown_option": "QuestionValidationException",
        "missing_snapshot": type(error.value).__name__,
    }


def test_public_work_handle_and_answer_recovery(snapshots):
    session = snapshots["a"]
    question = session.q.nodeProperties(properties="Configuration_Format", question_name="mvp01-background")
    started = time.monotonic()
    work_id = question.answer(snapshot="snapshot-a", background=True)
    UUID(work_id)
    submitted_seconds = time.monotonic() - started
    restored = Session(host=snapshots["host"], port=snapshots["port"], timeout=10)
    restored.set_network(session.network)
    observed = []
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status = restored.get_work_status(work_id)
        observed.append(status["workstatus"])
        if status["workstatus"] in {"TERMINATEDNORMALLY", "TERMINATEDABNORMALLY", "ASSIGNMENTERROR", "REQUEUEFAILURE"}:
            break
        time.sleep(0.1)
    assert observed[-1] == "TERMINATEDNORMALLY", observed
    recovered = restored.get_answer(question.get_name(), "snapshot-a")
    assert set(recovered.frame().Node) == {"r1", "r2"}
    assert restored.get_snapshot_input_object_text("configs/r1.cfg", snapshot="snapshot-a") == (FIXTURE / "configs" / "r1.cfg").read_text()
    snapshots["evidence"]["observations"]["background"] = {
        "work_id_type": type(work_id).__name__, "submission_seconds": round(submitted_seconds, 4),
        "observed_statuses": observed, "recovered_question": question.get_name(),
        "incomplete_works": restored.list_incomplete_works(),
    }


def test_request_timeout_is_not_a_total_work_budget(baseline, caplog):
    # A slow HTTP endpoint demonstrates automatic GET retries, not engine cancellation.
    finished = Event()
    requests_received = []

    class SlowHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests_received.append(time.monotonic())
            # Once the first slow request finishes, subsequent retries can succeed.
            finished.wait(0.2)
            self.send_response(200)
            self.end_headers()
            try:
                self.wfile.write(b'{"Batfish":"delayed"}')
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                finished.set()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        session = Session(host="127.0.0.1", port=server.server_port, load_questions=False, timeout=0.03)
        started = time.monotonic()
        assert session.get_component_versions() == {"Batfish": "delayed"}
        elapsed = time.monotonic() - started
        assert len(requests_received) >= 2
        assert elapsed > session.timeout
        assert any("Read timed out" in record.getMessage() for record in caplog.records)
        assert finished.wait(2), "Server request should continue after the client timeout"
        assert Session(load_questions=False).timeout == 30
        baseline["evidence"]["observations"]["timeout"] = {
            "sdk_default_seconds": 30, "configured_transport_seconds": 0.03,
            "read_timeout_retried": True, "http_requests": len(requests_received),
            "total_seconds": round(elapsed, 4), "server_request_continued": True,
            "scope": "controlled local HTTP only; not an engine work cancellation test",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
