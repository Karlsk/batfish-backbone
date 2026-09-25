from dataclasses import dataclass, field
from typing import BinaryIO
from uuid import UUID

from pydantic import AwareDatetime

from app.contracts.base import Contract


@dataclass(frozen=True)
class UploadInput:
    filename: str
    stream: BinaryIO = field(repr=False)


@dataclass(frozen=True)
class UploadLimits:
    max_bytes: int = 100 * 1024 * 1024
    max_expanded_bytes: int = 500 * 1024 * 1024
    max_files: int = 5000


class FileEntry(Contract):
    id: UUID
    path: str
    sha256: str
    size_bytes: int
    encoding: str
    line_count: int | None


class UploadManifest(Contract):
    upload_id: UUID
    network_id: UUID
    storage_key: str
    files: tuple[FileEntry, ...]


class UploadDTO(Contract):
    id: UUID
    network_id: UUID
    owner_id: UUID
    manifest: UploadManifest
    content_hash: str
    storage_key: str
    expires_at: AwareDatetime
    consumed_at: AwareDatetime | None = None
