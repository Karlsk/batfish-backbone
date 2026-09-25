"""Private immutable files. Never accepts a caller-supplied filesystem path as a key."""

import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def validate_key(key: str) -> str:
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("Invalid internal storage key")
    return key


class PendingFile:
    def __init__(self, directory: int, temporary: str, key: str):
        self._directory = directory
        self._temporary = temporary
        self._key = validate_key(key)
        self._published = False

    @property
    def key(self) -> str:
        return self._key

    def publish(self) -> None:
        if self._published:
            raise RuntimeError("File already published")
        # link is atomic and fails if the immutable destination already exists.
        os.link(
            self._temporary,
            validate_key(self._key),
            src_dir_fd=self._directory,
            dst_dir_fd=self._directory,
            follow_symlinks=False,
        )
        os.fsync(self._directory)
        self._published = True


class FileStore:
    def __init__(self, root: Path):
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        mode = os.fstat(self._directory).st_mode
        if mode & 0o077:
            os.close(self._directory)
            raise ValueError("Storage directory must be private (mode 0700)")

    @contextmanager
    def stage(self, key: str, content: bytes) -> Iterator[PendingFile]:
        key = validate_key(key)
        temporary = ".tmp-" + uuid4().hex
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=self._directory,
        )
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            yield PendingFile(self._directory, temporary, key)
        finally:
            os.unlink(temporary, dir_fd=self._directory)

    def read(self, key: str) -> bytes:
        fd = os.open(
            validate_key(key), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._directory
        )
        with os.fdopen(fd, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise OSError("Storage entry is not a regular file")
            return source.read()

    def delete(self, key: str) -> None:
        key = validate_key(key)
        info = os.stat(key, dir_fd=self._directory, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise OSError("Storage entry is not a regular file")
        os.unlink(key, dir_fd=self._directory)
        os.fsync(self._directory)

    def close(self) -> None:
        if self._directory >= 0:
            os.close(self._directory)
            self._directory = -1

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
