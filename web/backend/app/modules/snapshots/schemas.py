from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue, StrictBool

from app.contracts.base import Contract
from app.contracts.snapshots import (
    InitializationAnswer as InitializationAnswer,
)
from app.contracts.snapshots import (
    SnapshotCreated as SnapshotCreated,
)
from app.contracts.uploads import FileEntry, UploadManifest


class InitializationOptions(Contract):
    ignore_management_interfaces: StrictBool = True
    parse_reuse: StrictBool = False


class CreateSnapshotRequest(Contract):
    display_name: str = Field(min_length=1, max_length=255, pattern=r".*\S.*")
    upload_id: UUID
    options: InitializationOptions = Field(default_factory=InitializationOptions)


class SnapshotDTO(Contract):
    id: UUID
    network_id: UUID
    engine_name: str
    display_name: str
    content_hash: str
    base_snapshot_id: UUID | None = None
    initialization_job_id: UUID | None
    status: Literal[
        "queued", "initializing", "ready", "ready_with_warnings", "failed", "deleting", "deleted"
    ]
    quality_summary: Mapping[str, JsonValue]
    engine_version: str | None
    sdk_version: str | None
    deletion_job_id: UUID | None = None
    created_by: UUID
    created_at: AwareDatetime


class StoredSnapshot(SnapshotDTO):
    manifest: UploadManifest | None
    initialization_options: InitializationOptions
    diagnostics: Mapping[str, JsonValue]


class SnapshotPage(Contract):
    items: tuple[SnapshotDTO, ...]
    total: int
    offset: int
    limit: int


class SourceLocation(Contract):
    file_id: UUID | None
    path: str
    lines: tuple[int, ...] = ()


class Diagnostic(Contract):
    source: Literal["fileParseStatus", "initIssues", "parseWarning", "viConversionWarning"]
    severity: Literal["info", "warning", "error"]
    status: str | None = None
    description: str
    locations: tuple[SourceLocation, ...] = ()
    raw: Mapping[str, JsonValue]


class DiagnosticPage(Contract):
    items: tuple[Diagnostic, ...]
    offset: int
    limit: int
    total: int


class SnapshotFiles(Contract):
    items: tuple[FileEntry, ...]
