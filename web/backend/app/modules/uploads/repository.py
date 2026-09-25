import os
import re
import shutil
import stat
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.contracts.errors import ServiceError
from app.modules.uploads.archive import prepare, safe_path
from app.modules.uploads.models import Upload
from app.modules.uploads.schemas import UploadDTO, UploadManifest


class UploadsRepository:
    def __init__(self, transaction):
        self._transaction = transaction

    def add(self, dto: UploadDTO):
        self._transaction.add(
            Upload(
                **dto.model_dump(exclude={"manifest"}),
                manifest=dto.manifest.model_dump(mode="json"),
            )
        )
        self._transaction.flush()

    def locked(self, upload_id):
        row = self._transaction.scalar(
            select(Upload).where(Upload.id == upload_id).with_for_update()
        )
        if row is None:
            return None
        return UploadDTO(
            id=row.id,
            network_id=row.network_id,
            owner_id=row.owner_id,
            manifest=UploadManifest.model_validate(row.manifest),
            content_hash=row.content_hash,
            storage_key=row.storage_key,
            expires_at=row.expires_at,
            consumed_at=row.consumed_at,
        )

    def mark_consumed(self, upload_id, now):
        self._transaction.get(Upload, upload_id).consumed_at = now

    def expired(self, now):
        return self._transaction.scalars(
            select(Upload)
            .where(Upload.consumed_at.is_(None), Upload.expires_at <= now)
            .with_for_update(skip_locked=True)
        ).all()

    def remove(self, row):
        self._transaction.delete(row)

    def storage_keys(self):
        return set(self._transaction.scalars(select(Upload.storage_key)))


class UploadStore:
    def __init__(self, data_dir: Path):
        self.root = data_dir / "uploads"

    def ensure_root(self):
        self.root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.parent.is_symlink():
            raise OSError("Invalid data directory")
        self.root.mkdir(mode=0o700, exist_ok=True)
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise OSError("Upload directory must be private")

    @contextmanager
    def prepare(self, upload_id, inputs, *, archive, limits):
        self.ensure_root()
        temporary = Path(tempfile.mkdtemp(prefix=".tmp-", dir=self.root))
        destination = self.root / str(upload_id)
        try:
            files, digest = prepare(inputs, archive=archive, root=temporary, limits=limits)

            def publish():
                # Flush database insertion first, publish complete files before DB commit.
                destination.mkdir(mode=0o700)
                try:
                    for child in temporary.iterdir():
                        os.rename(child, destination / child.name)
                    for directory in (destination, self.root):
                        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                        try:
                            os.fsync(fd)
                        finally:
                            os.close(fd)
                except BaseException:
                    shutil.rmtree(destination)
                    raise

            yield files, digest, publish
            # A DB commit error after publish can have an unknown outcome. Preserve files;
            # a later cleanup removes only old directories without a database reference.
        finally:
            shutil.rmtree(temporary)

    def remove(self, key):
        # Only internal UUIDs, and never follow a symbolic link for recursive deletion.
        name = str(UUID(key))
        path = self.root / name
        if path.is_symlink():
            raise OSError("Invalid upload directory")
        if path.exists():
            shutil.rmtree(path)

    def cleanup_orphans(self, referenced, *, now, ttl_seconds):
        self.ensure_root()
        threshold = (now - timedelta(seconds=ttl_seconds)).timestamp()
        for path in self.root.iterdir():
            if path.name in referenced or not re.fullmatch(
                r"(\.tmp-[A-Za-z0-9_-]+|[a-f0-9-]{36})", path.name
            ):
                continue
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode) and info.st_mtime < threshold:
                shutil.rmtree(path)

    @contextmanager
    def materialize(self, manifest):
        import hashlib
        from pathlib import PurePosixPath

        self.ensure_root()
        temporary = Path(tempfile.mkdtemp(prefix=".tmp-sdk-", dir=self.root))
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        source_fd = None
        try:
            source_fd = os.open(
                str(UUID(manifest.storage_key)),
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root_fd,
            )
            for item in manifest.files:
                logical = PurePosixPath(item.path)
                try:
                    canonical = safe_path(item.path)
                except ServiceError:
                    raise ValueError("Invalid stored manifest") from None
                if canonical != item.path:
                    raise ValueError("Invalid stored manifest")
                destination = temporary.joinpath(*logical.parts)
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                fd = os.open(str(item.id), os.O_RDONLY | os.O_NOFOLLOW, dir_fd=source_fd)
                with os.fdopen(fd, "rb") as source, destination.open("xb") as output:
                    os.chmod(destination, 0o600)
                    if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                        raise ValueError("Invalid stored file")
                    digest, size = hashlib.sha256(), 0
                    while chunk := source.read(65536):
                        size += len(chunk)
                        if size > item.size_bytes:
                            raise ValueError("Stored file changed")
                        digest.update(chunk)
                        output.write(chunk)
                    if size != item.size_bytes or digest.hexdigest() != item.sha256:
                        raise ValueError("Stored file changed")
            yield temporary
        finally:
            if source_fd is not None:
                os.close(source_fd)
            os.close(root_fd)
            shutil.rmtree(temporary)

    @contextmanager
    def open_verified(self, manifest, entry):
        import hashlib

        self.ensure_root()
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        directory_fd = None
        try:
            directory_fd = os.open(
                str(UUID(manifest.storage_key)),
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root_fd,
            )
            fd = os.open(str(entry.id), os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
            with os.fdopen(fd, "rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != entry.size_bytes:
                    raise ValueError("Stored file changed")
                if hashlib.file_digest(source, "sha256").hexdigest() != entry.sha256:
                    raise ValueError("Stored file changed")
                source.seek(0)
                yield source
        finally:
            if directory_fd is not None:
                os.close(directory_fd)
            os.close(root_fd)
