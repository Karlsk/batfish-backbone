"""Shared snapshot contracts used across service boundaries."""

from collections.abc import Mapping
from uuid import UUID

from pydantic import JsonValue

from app.contracts.base import Contract


class SnapshotCreated(Contract):
    snapshot_id: UUID
    job_id: UUID


class InitializationAnswer(Contract):
    parse_status: tuple[Mapping[str, JsonValue], ...]
    issues: tuple[Mapping[str, JsonValue], ...]
    engine_version: str
    sdk_version: str
    parse_warnings: tuple[Mapping[str, JsonValue], ...] = ()
    conversion_warnings: tuple[Mapping[str, JsonValue], ...] = ()
