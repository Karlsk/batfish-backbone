from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from .base import Contract
from .errors import ErrorDetail


class Actor(Contract):
    """Constructed by trusted authentication services, never from request bodies."""

    user_id: UUID
    role: Literal["admin", "member"]
    enabled: bool


class AnalysisContext(Contract):
    network_id: UUID
    snapshot_id: UUID
    reference_snapshot_id: UUID | None = None
    engine_network: str = Field(min_length=1)
    engine_snapshot: str = Field(min_length=1)
    engine_reference_snapshot: str | None = Field(default=None, min_length=1)
    engine_version: str = Field(min_length=1)
    sdk_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def reference_pair(self):
        if (self.reference_snapshot_id is None) != (self.engine_reference_snapshot is None):
            raise ValueError("Reference snapshot ID and engine name must be supplied together")
        return self


class JobDTO(Contract):
    id: UUID
    kind: Literal["upload", "initialization", "analysis", "deletion"]
    resource_ids: Mapping[str, UUID]
    requested_parameters: Mapping[str, JsonValue]
    effective_parameters: Mapping[str, JsonValue]
    created_by: UUID
    status: Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]
    phase: str
    attempt: int = Field(ge=0)
    lease_owner: str | None = None
    heartbeat_at: AwareDatetime | None = None
    engine_state: Literal["idle", "busy", "unknown"]
    cancel_allowed: bool
    result_id: UUID | None = None
    error: ErrorDetail | None = None
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None


class ResultEnvelope(Contract):
    id: UUID
    kind: Literal["table", "traces", "graph", "diff"]
    schema_version: str = Field(min_length=1)
    context: AnalysisContext
    effective_parameters: Mapping[str, JsonValue]
    summary: Mapping[str, JsonValue]
    warnings: tuple[str, ...]
    coverage: Literal["complete", "limited", "unknown"]
    truncated: bool
    truncation_reason: str | None = Field(default=None, min_length=1)
    created_at: AwareDatetime

    @model_validator(mode="after")
    def require_truncation_reason(self):
        if self.truncated and self.truncation_reason is None:
            raise ValueError("Truncated results require an explanation")
        return self
