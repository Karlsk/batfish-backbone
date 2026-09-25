from uuid import UUID

import pytest

from app.contracts.errors import ServiceError
from tests import test_networks
from tests.test_snapshots import create, setup
from tests.test_uploads import upload

pytestmark = pytest.mark.integration
snapshot_app = test_networks.network_app


def test_file_access_bounds_and_original_lines(snapshot_app):
    client, db, app, headers, network, source, actor = setup(snapshot_app)
    data = "sysname 交换机\r\n#\nlast".encode("gb18030")
    source = upload(client, headers, network, files=[("original.cfg", data)]).json()
    queued = create(client, headers, network, source).json()
    base = f"/api/v1/networks/{network}/snapshots/{queued['snapshot_id']}"
    response = client.get(base + "/files")
    assert response.status_code == 200
    files = response.json()["items"]
    assert len(files) == 1 and files[0]["path"] == "configs/original.cfg"
    file_url = base + "/files/" + files[0]["id"]
    page = client.get(file_url, params={"offset": 1, "limit": 2}).json()
    assert page["lines"] == [
        {"number": 2, "text": "#", "truncated": False},
        {"number": 3, "text": "last", "truncated": False},
    ]
    assert page["total"] == 3 and page["encoding"] == "gb18030"
    assert client.get(file_url, params={"offset": -1}).status_code == 422
    assert client.get(file_url, params={"limit": 201}).status_code == 422
    assert client.get(file_url, params={"offset": 99}).json()["lines"] == []
    other = create(client, headers, network, upload(client, headers, network).json()).json()
    assert (
        client.get(
            f"/api/v1/networks/{network}/snapshots/{other['snapshot_id']}/files/{files[0]['id']}"
        ).status_code
        == 404
    )
    assert client.get(base + "/diagnostics").status_code == 409
    assert (
        "storage_key" not in response.text
        and str(app.state.uploads_service.storage_root) not in response.text
    )


def test_missing_source_line_and_diagnostic_pagination(snapshot_app, monkeypatch):
    from app.modules.snapshots.schemas import InitializationAnswer

    client, db, app, headers, network, source, actor = setup(snapshot_app)
    queued = create(client, headers, network, source).json()
    answer = InitializationAnswer(
        parse_status=(
            {
                "File_Name": "configs/r1.cfg",
                "File_Format": "HUAWEI_VRP",
                "Status": "PARTIALLY_UNRECOGNIZED",
                "Nodes": ["r1"],
            },
        ),
        issues=(
            {"Type": "Parse warning", "Details": "No location supplied", "Source_Lines": None},
        ),
        engine_version="test",
        sdk_version="test",
    )
    monkeypatch.setattr(app.state.snapshots_service._controller, "initialize", lambda *args: answer)
    assert app.state.execution_service.run_once("worker")
    base = f"/api/v1/networks/{network}/snapshots/{queued['snapshot_id']}"
    page = client.get(
        base + "/diagnostics", params={"limit": 1, "offset": 1, "severity": "warning"}
    )
    assert page.status_code == 200
    row = page.json()["items"][0]
    assert row["source"] == "initIssues" and row["locations"] == []
    assert row["raw"]["Type"] == "Parse warning" and page.json()["total"] == 2
    assert client.get(base + "/diagnostics", params={"severity": "nonsense"}).status_code == 422


@pytest.mark.parametrize("status", ["FAILED", "UNKNOWN", "UNSUPPORTED"])
def test_unsupported_parse_blocks_analysis(snapshot_app, monkeypatch, status):
    from app.modules.snapshots.schemas import InitializationAnswer

    client, db, app, headers, network, source, actor = setup(snapshot_app)
    queued = create(client, headers, network, source).json()
    answer = InitializationAnswer(
        parse_status=({"Status": status, "Nodes": ["r1"]},),
        issues=(),
        engine_version="test",
        sdk_version="test",
    )
    monkeypatch.setattr(app.state.snapshots_service._controller, "initialize", lambda *args: answer)
    assert app.state.execution_service.run_once("worker")
    with pytest.raises(ServiceError):
        app.state.snapshots_service.require_analyzable(
            actor, UUID(network), UUID(queued["snapshot_id"])
        )


def test_vendor_limits_visible_when_passed(snapshot_app, monkeypatch):
    from app.modules.snapshots.schemas import InitializationAnswer

    client, db, app, headers, network, source, actor = setup(snapshot_app)
    queued = create(client, headers, network, source).json()
    answer = InitializationAnswer(
        parse_status=({"Status": "PASSED", "Nodes": ["r1"], "File_Format": "H3C_COMWARE"},),
        issues=(),
        engine_version="test",
        sdk_version="test",
    )
    monkeypatch.setattr(app.state.snapshots_service._controller, "initialize", lambda *args: answer)
    assert app.state.execution_service.run_once("worker")
    detail = client.get(f"/api/v1/networks/{network}/snapshots/{queued['snapshot_id']}").json()
    quality = detail["quality_summary"]
    assert quality["coverage"] == "limited"
    assert quality["parse_statuses"] == ["PASSED"]
    assert {"ipv6", "srv6", "evpn", "acl"} <= {
        item["capability"] for item in quality["model_limits"]
    }
    assert all(
        item["status"] in {"limited", "unknown", "unsupported"} for item in quality["model_limits"]
    )


def test_binary_and_long_line_are_explicit(snapshot_app):
    client, db, app, headers, network, source, actor = setup(snapshot_app)
    source = upload(
        client,
        headers,
        network,
        files=[("binary.cfg", b"\x81"), ("long.cfg", b"x" * 70000 + b"\nnext\n")],
    ).json()
    queued = create(client, headers, network, source).json()
    base = f"/api/v1/networks/{network}/snapshots/{queued['snapshot_id']}"
    files = client.get(base + "/files").json()["items"]
    for file in files:
        page = client.get(base + "/files/" + file["id"]).json()
        if file["path"].endswith("binary.cfg"):
            assert page["lines"] == [] and page["warnings"] == ["BINARY_CONTENT_NOT_DISPLAYABLE"]
        else:
            assert page["lines"][0]["truncated"] is True
            assert len(page["lines"][0]["text"]) == 65536
            assert page["lines"][1]["number"] == 2 and page["lines"][1]["text"] == "next"
            assert page["warnings"] == ["LONG_LINE_TRUNCATED"]


def test_real_diagnostics_preserve_source_locations(snapshot_app):
    from pathlib import Path

    client, db, app, headers, network, source, actor = setup(snapshot_app)
    fixture = Path(__file__).parent / "fixtures" / "small_network" / "configs"
    files = [
        (p.name, p.read_bytes().replace(b"return", b"mvp11-unsupported-command\nreturn"))
        for p in sorted(fixture.iterdir())
    ]
    source = upload(client, headers, network, files=files).json()
    queued = create(client, headers, network, source).json()
    assert app.state.execution_service.run_once("worker")
    base = f"/api/v1/networks/{network}/snapshots/{queued['snapshot_id']}"
    detail = client.get(base).json()
    assert detail["status"] == "ready_with_warnings" and detail["quality_summary"]["model_limits"]
    diagnostics = client.get(base + "/diagnostics", params={"severity": "warning"}).json()["items"]
    assert {"initIssues", "parseWarning"} <= {item["source"] for item in diagnostics}
    for item in diagnostics:
        if item["source"] not in {"initIssues", "parseWarning"}:
            continue
        assert item["locations"], item
        for position in item["locations"]:
            assert position["lines"] and position["file_id"]
            page = client.get(
                base + "/files/" + position["file_id"],
                params={"offset": position["lines"][0] - 1, "limit": 1},
            ).json()
            assert page["lines"][0]["number"] == position["lines"][0]
            assert "mvp11-unsupported-command" in page["lines"][0]["text"]


def test_existing_snapshot_applies_new_quality_policy(snapshot_app, monkeypatch):
    from sqlalchemy import text

    from app.modules.snapshots.schemas import InitializationAnswer

    client, db, app, headers, network, source, actor = setup(snapshot_app)
    queued = create(client, headers, network, source).json()
    answer = InitializationAnswer(
        parse_status=({"Status": "UNKNOWN", "Nodes": ["r1"]},),
        issues=(),
        engine_version="test",
        sdk_version="test",
    )
    monkeypatch.setattr(app.state.snapshots_service._controller, "initialize", lambda *args: answer)
    assert app.state.execution_service.run_once("worker")
    # Simulate a snapshot/job saved as usable by the MVP-10 policy.
    with db.transaction() as tx:
        tx.execute(
            text("UPDATE jobs SET status='succeeded', error=NULL WHERE id=:id"),
            {"id": queued["job_id"]},
        )
        tx.execute(
            text("UPDATE snapshots SET status='ready_with_warnings' WHERE id=:id"),
            {"id": queued["snapshot_id"]},
        )
    with pytest.raises(ServiceError):
        app.state.snapshots_service.require_analyzable(
            actor, UUID(network), UUID(queued["snapshot_id"])
        )


@pytest.mark.parametrize("ending", [b"\r", b"\r\r\n", b"\r\n"])
def test_real_cr_source_lines_and_legacy_manifest(snapshot_app, ending):
    import json
    from pathlib import Path

    from sqlalchemy import text

    client, db, app, headers, network, source, actor = setup(snapshot_app)
    fixture = Path(__file__).parent / "fixtures" / "small_network" / "configs"
    files = []
    for p in sorted(fixture.iterdir()):
        data = p.read_bytes().replace(b"return", b"mvp11-unsupported-command\nreturn")
        # Mix LF with CR/CRLF/CR-run endings while preserving source row sequence.
        data = ending.join(data.split(b"\n")[:3]) + b"\n" + ending.join(data.split(b"\n")[3:])
        files.append((p.name, data))
    source = upload(client, headers, network, files=files).json()
    assert source["manifest"]["files"][0]["line_count"] > 3
    queued = create(client, headers, network, source).json()
    # Previously persisted manifests had LF-only counts: file view must repair presentation.
    with db.transaction() as tx:
        old = source["manifest"]
        for entry in old["files"]:
            entry["line_count"] = 1
            entry["line_policy"] = "lf-v0"
        tx.execute(
            text("UPDATE snapshots SET manifest=CAST(:manifest AS jsonb) WHERE id=:id"),
            {"manifest": json.dumps(old), "id": queued["snapshot_id"]},
        )
    assert app.state.execution_service.run_once("worker")
    base = f"/api/v1/networks/{network}/snapshots/{queued['snapshot_id']}"
    assert client.get(base).json()["status"] == "ready_with_warnings"
    entries = client.get(base + "/files").json()["items"]
    assert all(entry["line_count"] > 3 for entry in entries)
    diagnostics = client.get(base + "/diagnostics", params={"severity": "warning"}).json()["items"]
    warnings = [item for item in diagnostics if item["source"] == "parseWarning"]
    assert warnings
    for item in warnings:
        assert item["locations"][0]["lines"]
        position = item["locations"][0]
        page = client.get(
            base + "/files/" + position["file_id"],
            params={"offset": position["lines"][0] - 1, "limit": 1},
        ).json()
        assert "mvp11-unsupported-command" in page["lines"][0]["text"] and page["total"] > 3
