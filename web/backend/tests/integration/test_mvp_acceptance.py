"""End-to-end API/SDK equivalence with measured, explicitly small configuration samples."""

import json
import os
import subprocess
import threading
import time
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pybatfish.datamodel import HeaderConstraints

from app.infrastructure.sdk import SessionFactory
from app.infrastructure.settings import Settings
from tests import test_networks
from tests.test_inventory import initialize

acceptance_app = test_networks.network_app


def sdk_json(value):
    """Independent comparison serializer; does not call the application's result mapper."""

    def encode(item):
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, (set, frozenset)):
            return sorted(item, key=str)
        if callable(getattr(item, "dict", None)):
            return item.dict()
        raise TypeError(type(item).__name__)

    return json.loads(json.dumps(value, default=encode, allow_nan=False))


def canonical(rows):
    return sorted(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows)


class MemorySamples:
    def __init__(self, manifest):
        rows = subprocess.check_output(["ps", "-axo", "pid=,ppid=,rss=,comm="], text=True)
        engines = [
            int(parts[0])
            for line in rows.splitlines()
            if len(parts := line.strip().split(None, 3)) == 4
            and int(parts[1]) == manifest["manager_pid"]
            and Path(parts[3]).name == "java"
        ]
        assert len(engines) == 1, "Expected the owned lab Java child"
        self.pids = {"python_test_worker": os.getpid(), "engine": engines[0]}
        self.peak = {name: 0 for name in self.pids}
        self.stop = threading.Event()
        self.error = None

    def sample(self):
        rows = subprocess.check_output(
            ["ps", "-o", "pid=,rss=", "-p", ",".join(str(p) for p in self.pids.values())], text=True
        )
        rss = {int(a): int(b) * 1024 for a, b in (line.split() for line in rows.splitlines())}
        for name, pid in self.pids.items():
            self.peak[name] = max(self.peak[name], rss[pid])

    def run(self):
        while not self.stop.wait(0.1):
            try:
                self.sample()
            except Exception as error:
                self.error = error
                return

    def __enter__(self):
        self.sample()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        assert self.error is None
        self.sample()


@pytest.mark.integration
@pytest.mark.parametrize("fixture", ["small_network", "cisco_four"])
def test_mvp_full_sdk_equivalence_and_measured_scale(acceptance_app, fixture):
    manifest = json.loads(Path(os.environ["BATFISH_LAB_MANIFEST"]).read_text())
    measurements = []
    with MemorySamples(manifest) as memory:
        started = time.perf_counter()
        state = initialize(acceptance_app, fixture)
    measurements.append(
        {
            "operation": "initialize",
            "seconds": time.perf_counter() - started,
            "sampled_peak_rss_bytes": memory.peak,
        }
    )
    client, db, app, headers, network, snapshot, actor = state
    context = app.state.snapshots_service.require_analyzable(actor, UUID(network), UUID(snapshot))
    session_factory = SessionFactory(
        db, Settings(batfish_host=manifest["host"], batfish_port=manifest["engine_port"])
    )
    start, ip = ("r1", "10.0.0.2") if fixture == "small_network" else ("c1", "10.64.0.4")
    cases = [
        (
            "nodes",
            {"options": {"properties": ["Hostname", "Configuration_Format", "Interfaces"]}},
            "nodeProperties",
            {"properties": "Hostname,Configuration_Format,Interfaces"},
        ),
        (
            "interfaces",
            {"options": {"properties": ["Active", "Primary_Address", "VRF"]}},
            "interfaceProperties",
            {"properties": "Active,Primary_Address,VRF"},
        ),
        ("routes", {}, "routes", {"rib": "main", "prefixMatchType": "EXACT"}),
        ("lpm-routes", {"ip": ip}, "lpmRoutes", {"ip": ip}),
        (
            "traceroute",
            {"start_location": start, "destination_ip": ip},
            "traceroute",
            {
                "startLocation": start,
                "headers": HeaderConstraints(dstIps=ip, ipProtocols=["icmp"]),
                "maxTraces": 5,
                "ignoreFilters": False,
            },
        ),
    ]
    for operation, body, sdk_question, parameters in cases:
        base = f"/api/v1/networks/{network}/snapshots/{snapshot}/analyses/{operation}"
        with MemorySamples(manifest) as memory:
            started = time.perf_counter()
            submitted = client.post(base, json=body, headers=headers)
            assert submitted.status_code == 202
            assert app.state.execution_service.run_once("acceptance-worker")
            job = client.get("/api/v1/jobs/" + submitted.json()["id"]).json()
            assert job["status"] == "succeeded"
            response = client.get("/api/v1/results/" + job["result_id"] + "/export")
            assert response.status_code == 200
            data = response.json()
            elapsed = time.perf_counter() - started
        with session_factory.for_job(context) as session:
            direct = sdk_json(
                getattr(session.q, sdk_question)(**parameters)
                .answer(snapshot=context.engine_snapshot)
                .dict()
            )["answerElements"][0]
        if operation == "traceroute":
            actual = [
                {"Flow": f["headers"], "TraceCount": f["trace_count"], "Traces": f["traces"]}
                for f in data["data"]["flows"]
            ]
        else:
            actual = data["data"]["rows"]
            assert {c["key"] for c in data["data"]["columns"]} == {
                c["name"] for c in direct["metadata"]["columnMetadata"]
            }
        assert canonical(actual) == canonical(direct["rows"])
        assert data["metadata"]["context"]["snapshot_id"] == snapshot
        assert not data["metadata"]["truncated"]
        # Expert explicit defaults and basic minimal input canonicalize to the same result.
        explicit = job["effective_parameters"]["request"]
        second = client.post(base, json=explicit, headers=headers)
        assert second.status_code == 202 and app.state.execution_service.run_once(
            "acceptance-worker"
        )
        equivalent = client.get("/api/v1/jobs/" + second.json()["id"]).json()
        assert equivalent["status"] == "succeeded" and equivalent["result_id"] == job["result_id"]
        measurements.append(
            {
                "operation": operation,
                "seconds": elapsed,
                "export_bytes": len(response.content),
                "saved_rows_or_flows": len(actual),
                "sampled_peak_rss_bytes": memory.peak,
                "sdk_comparison": "equal",
                "basic_expert": "equal",
            }
        )
    output = Path(manifest["run_directory"]) / "acceptance"
    output.mkdir(exist_ok=True)
    report = {
        "fixture": fixture,
        "devices": 2 if fixture == "small_network" else 4,
        "network_id": network,
        "snapshot_id": snapshot,
        "context": context.model_dump(mode="json"),
        "engine_revision": manifest["engine_revision"],
        "jar_sha256": manifest["jar_sha256"],
        "measurements": measurements,
        "memory_method": "100ms ps RSS sampling; warm shared lab JVM and in-process Python test worker; sampled peak, not process allocation or capacity guarantee",
        "status": "passed",
    }
    (output / (fixture + "-" + uuid4().hex + ".json")).write_text(
        json.dumps(report, indent=2) + "\n"
    )
