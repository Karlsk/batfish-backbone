import zipfile

import pytest
from lab import PROFILES, archive_snapshot, snapshot_digest


@pytest.mark.parametrize("name,count", [("r1-r2", 2), ("cisco-four", 4)])
def test_lab_uploads_contain_exact_config_bytes(name, count, tmp_path):
    source = PROFILES[name]["source"]
    configs = sorted((source / "configs").glob("*"))
    assert len(configs) == count
    archive = archive_snapshot(source, tmp_path / f"{name}.zip")
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == {f"configs/{p.name}" for p in configs}
        for path in configs:
            assert bundle.read(f"configs/{path.name}") == path.read_bytes()


def test_snapshot_identity_changes_with_content_and_filename(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    path = configs / "r1.cfg"
    path.write_text("hostname r1\n")
    first = snapshot_digest(tmp_path)
    assert first == snapshot_digest(tmp_path)
    path.write_text("hostname changed\n")
    second = snapshot_digest(tmp_path)
    assert first != second
    path.rename(configs / "renamed.cfg")
    assert snapshot_digest(tmp_path) != second


def test_lab_archive_rejects_symlinked_inputs(tmp_path):
    source = tmp_path / "snapshot"
    configs = source / "configs"
    configs.mkdir(parents=True)
    outside = tmp_path / "outside.cfg"
    outside.write_text("do not package arbitrary files")
    (configs / "r1.cfg").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        archive_snapshot(source, tmp_path / "bad.zip")


def test_lab_operation_lock_prevents_overlapping_runs(tmp_path):
    import lab

    with lab.exclusive_run(tmp_path / "operations.lock"):
        with pytest.raises(RuntimeError, match="already running"):
            with lab.exclusive_run(tmp_path / "operations.lock"):
                pytest.fail("Overlapping engine operation was allowed")
    with lab.exclusive_run(tmp_path / "operations.lock"):
        pass  # The lock is released, including after an exception.
