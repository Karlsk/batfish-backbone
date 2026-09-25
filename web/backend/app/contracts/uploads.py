from uuid import UUID

from app.contracts.base import Contract


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
    content_hash: str = ""
