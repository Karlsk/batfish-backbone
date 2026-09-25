import os

import pytest

from app.infrastructure.storage import FileStore


@pytest.mark.parametrize(
    "key", ["", ".", "..", "../escape", "/tmp/escape", "a/b", "a\\b", "a\x00b", ".tmp-x"]
)
def test_storage_key_boundary(tmp_path, key):
    with FileStore(tmp_path / "private") as store:
        with pytest.raises(ValueError):
            with store.stage(key, b"data"):
                pass
        with pytest.raises(ValueError):
            store.read(key)
        with pytest.raises(ValueError):
            store.delete(key)


def test_atomic_publication_and_no_overwrite(tmp_path):
    with FileStore(tmp_path / "private") as store:
        with store.stage("result-1", b"complete result") as pending:
            with pytest.raises(FileNotFoundError):
                store.read("result-1")
            pending.publish()
            assert store.read("result-1") == b"complete result"
        with pytest.raises(FileExistsError):
            with store.stage("result-1", b"replacement") as pending:
                pending.publish()
        assert store.read("result-1") == b"complete result"
        assert sorted(p.name for p in (tmp_path / "private").iterdir()) == ["result-1"]
        store.delete("result-1")
        with pytest.raises(FileNotFoundError):
            store.read("result-1")


def test_failed_stage_cleanup(tmp_path, monkeypatch):
    root = tmp_path / "private"
    with FileStore(root) as store:
        with pytest.raises(RuntimeError):
            with store.stage("failed", b"data"):
                raise RuntimeError("database rejected metadata")
        assert list(root.iterdir()) == []

        def fail_sync(_fd):
            raise OSError("disk failure")

        monkeypatch.setattr(os, "fsync", fail_sync)
        with pytest.raises(OSError):
            with store.stage("disk-failure", b"data"):
                pass
        assert list(root.iterdir()) == []


def test_symlinks_cannot_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.write_bytes(b"private data")
    root = tmp_path / "private"
    with FileStore(root) as store:
        (root / "link").symlink_to(outside)
        with pytest.raises(OSError):
            store.read("link")
        with pytest.raises(OSError):
            store.delete("link")
        with pytest.raises(FileExistsError):
            with store.stage("link", b"overwrite") as pending:
                pending.publish()
    assert outside.read_bytes() == b"private data"
    alias = tmp_path / "alias"
    alias.symlink_to(root)
    with pytest.raises(OSError):
        FileStore(alias)


def test_root_replacement_keeps_directory_boundary(tmp_path):
    root = tmp_path / "private"
    with FileStore(root) as store:
        root.rename(tmp_path / "original")
        outside = tmp_path / "outside"
        outside.mkdir()
        root.symlink_to(outside)
        with store.stage("result", b"safe") as pending:
            pending.publish()
        assert store.read("result") == b"safe"
        assert list(outside.iterdir()) == []


def test_pending_key_cannot_be_replaced(tmp_path):
    with FileStore(tmp_path / "private") as store:
        with store.stage("safe", b"data") as pending:
            with pytest.raises(AttributeError):
                pending.key = "../escape"
            pending.publish()
        assert store.read("safe") == b"data"
    assert not (tmp_path / "escape").exists()
