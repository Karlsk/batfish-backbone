from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue, StrictInt, model_validator

from app.contracts.base import Contract


class CreateBriefingRequest(Contract):
    title: str = Field(min_length=1, max_length=200, pattern=r".*\S.*")
    network_id: UUID
    snapshot_id: UUID
    result_ids: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    comparison_id: UUID | None = None
    concern_id: UUID | None = None
    concern_version: StrictInt | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def references(self):
        if len(set(self.result_ids)) != len(self.result_ids):
            raise ValueError("Result IDs must be unique")
        if (self.concern_id is None) != (self.concern_version is None):
            raise ValueError("Concern ID and version must be supplied together")
        return self


class ReviseBriefingRequest(Contract):
    expected_version: StrictInt = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200, pattern=r".*\S.*")
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def editorial_change(self):
        if not ({"title", "notes"} & self.model_fields_set):
            raise ValueError("A title or note change is required")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("Title cannot be empty")
        return self


class BriefingSection(Contract):
    result_id: UUID
    kind: Literal["table", "traces", "graph", "diff"]
    schema_version: str
    effective_parameters: Mapping[str, JsonValue]
    summary: Mapping[str, JsonValue]
    warnings: tuple[str, ...]
    coverage: Literal["complete", "limited", "unknown"]
    truncated: bool
    truncation_reason: str | None
    engine_version: str
    sdk_version: str
    created_at: AwareDatetime
    evidence_available: bool


class Briefing(Contract):
    id: UUID
    report_id: UUID
    version: int
    title: str
    notes: str | None
    network_id: UUID
    network_name: str
    snapshot_id: UUID
    snapshot_name: str
    snapshot_quality: Mapping[str, JsonValue]
    comparison_id: UUID | None
    frozen_comparison: Mapping[str, JsonValue] | None
    concern_id: UUID | None
    concern_version: int | None
    frozen_concern: Mapping[str, JsonValue] | None
    sections: tuple[BriefingSection, ...]
    warnings: tuple[str, ...]
    created_by: UUID
    created_at: AwareDatetime
    archived: bool
    source_available: bool


class BriefingPage(Contract):
    items: tuple[Briefing, ...]
    offset: int
    limit: int
    total: int
