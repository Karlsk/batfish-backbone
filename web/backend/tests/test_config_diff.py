"""Configuration diff jobs use immutable comparison direction and verified files."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.contracts.uploads import FileEntry, SourceLine
from tests import test_networks
from tests.test_comparisons import create_comparison
from tests.test_inventory import initialize
from tests.test_snapshots import create
from tests.test_uploads import upload

config_diff_app = test_networks.network_app


def candidate_with_file_changes(app_fixture):
    client, db, app, headers, network, baseline, actor = initialize(app_fixture, "cisco_four")
    folder = Path(__file__).parent / "fixtures/cisco_four/configs"
    files = []
    for path in sorted(folder.glob("*.cfg")):
        if path.name == "c4.cfg":
            files.append(("c5.cfg", path.read_bytes().replace(b"hostname c4", b"hostname c5")))
        elif path.name == "c1.cfg":
            files.append((path.name, path.read_bytes() + b"\n! candidate config marker\n"))
        else:
            files.append((path.name, path.read_bytes()))
    source = upload(client, headers, network, files=files).json()
    candidate_job = create(client, headers, network, source, display_name="Candidate")
    assert candidate_job.status_code == 202, candidate_job.text
    assert app.state.execution_service.run_once("worker")
    candidate = candidate_job.json()["snapshot_id"]
    candidate_state = client.get(f"/api/v1/networks/{network}/snapshots/{candidate}").json()
    assert candidate_state["status"] in {
        "ready",
        "ready_with_warnings",
    }, app.state.jobs_service.get(actor, UUID(candidate_job.json()["job_id"])).error
    comparison = create_comparison(client, headers, network, baseline, candidate)
    assert comparison.status_code == 201, comparison.text
    return client, db, app, headers, network, baseline, candidate, actor, comparison.json()


@pytest.mark.integration
def test_added_removed_changed_files_and_direction(config_diff_app):
    client, db, app, headers, network, baseline, candidate, actor, comparison = (
        candidate_with_file_changes(config_diff_app)
    )
    endpoint = f"/api/v1/comparisons/{comparison['id']}/analyses/config-diff"
    submitted = client.post(endpoint, json={}, headers=headers | {"Idempotency-Key": "diff-once"})
    assert submitted.status_code == 202, submitted.text
    assert submitted.json()["context"]["snapshot_id"] == candidate
    assert submitted.json()["context"]["reference_snapshot_id"] == baseline
    duplicate = client.post(endpoint, json={}, headers=headers | {"Idempotency-Key": "diff-once"})
    assert duplicate.status_code == 202 and duplicate.json()["id"] == submitted.json()["id"]
    assert app.state.execution_service.run_once("worker")
    job = app.state.jobs_service.get(actor, UUID(submitted.json()["id"]))
    assert job.status == "succeeded", job.error
    result_id = str(job.result_id)
    result = client.get(f"/api/v1/results/{result_id}").json()
    assert result["kind"] == "diff"
    assert result["context"]["snapshot_id"] == candidate
    assert result["context"]["reference_snapshot_id"] == baseline
    assert result["effective_parameters"]["comparison_id"] == comparison["id"]
    page = client.get(f"/api/v1/results/{result_id}/diff/files?limit=2").json()
    assert page["total"] == 3 and len(page["items"]) == 2
    full = client.get(f"/api/v1/results/{result_id}/diff/files?limit=10").json()
    files = {item["path"]: item for item in full["items"]}
    assert {path: item["change"] for path, item in files.items()} == {
        "configs/c1.cfg": "changed",
        "configs/c4.cfg": "removed",
        "configs/c5.cfg": "added",
    }
    changed = client.get(
        f"/api/v1/results/{result_id}/diff/files/{files['configs/c1.cfg']['file_id']}"
    ).json()
    assert changed["total"] >= 1
    assert any(
        line["text"] == "! candidate config marker"
        for hunk in changed["hunks"]
        for line in hunk["candidate_lines"]
    )
    assert all(hunk["baseline_start"] >= 1 for hunk in changed["hunks"])
    assert client.get(f"/api/v1/results/{result_id}/rows").status_code == 409
    assert (
        client.post(endpoint, json={"options": {"host": "remote"}}, headers=headers).status_code
        == 422
    )
    second = client.post(endpoint, json={}, headers=headers | {"Idempotency-Key": "diff-cache"})
    assert second.status_code == 202 and second.json()["id"] != submitted.json()["id"]
    assert app.state.execution_service.run_once("worker")
    reused = app.state.jobs_service.get(actor, UUID(second.json()["id"]))
    assert reused.status == "succeeded" and reused.result_id == job.result_id
    assert (
        client.delete(f"/api/v1/comparisons/{comparison['id']}", headers=headers).status_code == 204
    )
    assert client.get(f"/api/v1/results/{result_id}/diff/files").status_code == 200


def entry(path, data, *, encoding="utf-8", lines=1):
    import hashlib

    return FileEntry(
        id=uuid4(),
        path=path,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        encoding=encoding,
        line_count=lines,
    )


def test_encoding_and_line_endings_keep_original_hashes():
    from app.modules.changes.config_diff import file_difference

    baseline = entry("configs/r1.cfg", b"hostname r1\r\n")
    candidate = entry("configs/r1.cfg", b"hostname r1\n")
    summary, hunks = file_difference(
        baseline,
        candidate,
        (SourceLine(number=1, text="hostname r1"),),
        (SourceLine(number=1, text="hostname r1"),),
    )
    assert (
        summary["change"] == "changed" and summary["baseline_sha256"] != summary["candidate_sha256"]
    )
    assert hunks == []
    assert "DISPLAY_LINES_EQUAL_RAW_BYTES_DIFFER" in summary["warnings"]
    chinese = "hostname 交换机\n".encode("gb18030")
    changed = entry("configs/r1.cfg", chinese, encoding="gb18030")
    summary, hunks = file_difference(
        baseline,
        changed,
        (SourceLine(number=1, text="hostname r1"),),
        (SourceLine(number=1, text="hostname 交换机"),),
    )
    assert summary["candidate_encoding"] == "gb18030"
    assert hunks[0]["candidate_lines"][0] == {"number": 1, "text": "hostname 交换机"}


def test_large_and_binary_files_have_honest_summary():
    from app.modules.changes.config_diff import file_difference

    baseline = entry("configs/big.cfg", b"a" * (1024 * 1024 + 1), lines=2000)
    candidate = entry("configs/big.cfg", b"b" * (1024 * 1024 + 1), lines=2000)
    summary, hunks = file_difference(baseline, candidate, None, None)
    assert summary["change"] == "changed" and summary["detail_truncated"]
    assert "FILE_LIMIT" in summary["warnings"] and hunks == []
    binary = entry("configs/raw.cfg", b"\xff\x00", encoding="binary", lines=0)
    summary, hunks = file_difference(None, binary, None, None)
    assert summary["change"] == "added" and summary["detail_truncated"]
    assert "BINARY_CONTENT_NOT_DISPLAYABLE" in summary["warnings"] and hunks == []


def test_detail_budget_keeps_file_summary_without_reading_text():
    from app.modules.changes.config_diff import file_difference

    baseline = entry("configs/r1.cfg", b"old\n")
    candidate = entry("configs/r1.cfg", b"new\n")
    summary, hunks = file_difference(baseline, candidate, None, None, detail_allowed=False)
    assert summary["change"] == "changed"
    assert summary["detail_truncated"] and "DETAIL_BUDGET" in summary["warnings"]
    assert hunks == []
