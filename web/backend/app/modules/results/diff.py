"""Public paginated configuration-difference result contracts."""

from typing import Literal

from pydantic import Field

from app.contracts.base import Contract
from app.contracts.uploads import SourceLine


class DiffFileSummary(Contract):
    file_id: str = Field(min_length=64, max_length=64)
    path: str
    change: Literal["added", "removed", "changed"]
    baseline_sha256: str | None
    candidate_sha256: str | None
    baseline_encoding: str | None
    candidate_encoding: str | None
    baseline_size_bytes: int | None
    candidate_size_bytes: int | None
    baseline_line_count: int | None
    candidate_line_count: int | None
    detail_truncated: bool
    hunk_count: int
    warnings: tuple[str, ...] = ()


class DiffHunk(Contract):
    tag: Literal["replace", "insert", "delete"]
    baseline_start: int
    baseline_end: int
    candidate_start: int
    candidate_end: int
    baseline_lines: tuple[SourceLine, ...]
    candidate_lines: tuple[SourceLine, ...]


class DiffFilePage(Contract):
    items: tuple[DiffFileSummary, ...]
    offset: int
    limit: int
    total: int
    truncated: bool


class DiffFileDetail(Contract):
    file: DiffFileSummary
    hunks: tuple[DiffHunk, ...]
    offset: int
    limit: int
    total: int
    truncated: bool
