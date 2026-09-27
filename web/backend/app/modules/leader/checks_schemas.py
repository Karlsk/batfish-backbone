from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue, StrictInt, model_validator

from app.contracts.base import Contract
from app.contracts.errors import ErrorDetail


class CheckTemplate(Contract):
    id: str
    version: str
    title: str
    category: Literal["mvp", "advance"]
    capability: str | None
    required_scope: tuple[str, ...]
    scope_schema: Mapping[str, JsonValue]
    options_schema: Mapping[str, JsonValue]
    model_note: str


class CheckTemplatePage(Contract):
    items: tuple[CheckTemplate, ...]


class CreateCheckRunRequest(Contract):
    template_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")
    network_id: UUID
    snapshot_id: UUID
    scope: Mapping[str, JsonValue] = Field(default_factory=dict)
    options: Mapping[str, JsonValue] = Field(default_factory=dict)
    concern_id: UUID | None = None
    concern_version: StrictInt | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def concern_pair(self):
        if (self.concern_id is None) != (self.concern_version is None):
            raise ValueError("Concern ID and version must be supplied together")
        return self


class CheckRunJob(Contract):
    id: UUID
    status: Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]
    phase: str
    engine_state: Literal["idle", "busy", "unknown"]
    result_id: UUID | None
    error_code: str | None
    created_at: AwareDatetime
    finished_at: AwareDatetime | None


class CheckRun(Contract):
    id: UUID
    template_id: str
    template_version: str
    network_id: UUID
    snapshot_id: UUID
    concern_id: UUID | None
    concern_version: int | None
    frozen_concern: Mapping[str, JsonValue] | None
    snapshot_quality: Mapping[str, JsonValue]
    engine_version: str
    sdk_version: str
    effective_parameters: Mapping[str, JsonValue]
    job_ids: tuple[UUID, ...]
    jobs: tuple[CheckRunJob, ...]
    result_ids: tuple[UUID, ...]
    derived_snapshot_id: UUID | None
    status: Literal[
        "submitting",
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "interrupted",
        "result_unavailable",
    ]
    error: ErrorDetail | None
    error_code: str | None
    created_by: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime


class CheckRunStored(Contract):
    id: UUID
    created_by: UUID
    idempotency_key: str
    request_hash: str
    template_id: str
    template_version: str
    network_id: UUID
    snapshot_id: UUID
    concern_id: UUID | None
    concern_version: int | None
    frozen_concern: Mapping[str, JsonValue] | None
    snapshot_quality: Mapping[str, JsonValue]
    engine_version: str
    sdk_version: str
    effective_parameters: Mapping[str, JsonValue]
    job_ids: tuple[UUID, ...]
    derived_snapshot_id: UUID | None
    submission_state: Literal["submitting", "dispatched", "succeeded", "failed"]
    error_code: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class CheckRunPage(Contract):
    items: tuple[CheckRun, ...]
    offset: int
    limit: int
    total: int
