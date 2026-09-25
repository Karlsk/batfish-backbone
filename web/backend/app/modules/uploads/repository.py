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

from app.modules.uploads.archive import prepare
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
