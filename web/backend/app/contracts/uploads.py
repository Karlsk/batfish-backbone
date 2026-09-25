from typing import Literal
from uuid import UUID

from app.contracts.base import Contract


class FileEntry(Contract):
    id: UUID
    path: str
    sha256: str
    size_bytes: int
    encoding: str
    line_count: int | None
    line_policy: Literal["lf-v0", "crlf-v1"] = "lf-v0"


class UploadManifest(Contract):
    upload_id: UUID
    network_id: UUID
    storage_key: str
    files: tuple[FileEntry, ...]
    content_hash: str = ""


class SourceLine(Contract):
    number: int
    text: str
    truncated: bool = False


class FilePage(Contract):
    file_id: UUID
    path: str
    encoding: str
    lines: tuple[SourceLine, ...]
    offset: int
    limit: int
    total: int | None
    warnings: tuple[str, ...] = ()
