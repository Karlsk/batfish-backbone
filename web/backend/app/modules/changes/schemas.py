from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.contracts.base import Contract


class CreateComparisonRequest(Contract):
    baseline_snapshot_id: UUID
    candidate_snapshot_id: UUID
    display_name: str | None = Field(default=None, min_length=1, max_length=255, pattern=r".*\S.*")


class ComparisonDTO(Contract):
    id: UUID
    network_id: UUID
    baseline_snapshot_id: UUID
    candidate_snapshot_id: UUID
    display_name: str
    baseline_content_hash: str
    candidate_content_hash: str
    baseline_engine_version: str
    candidate_engine_version: str
    baseline_sdk_version: str
    candidate_sdk_version: str
    engine_version: str
    sdk_version: str
    coverage: Literal["complete", "limited"]
    coverage_notes: tuple[str, ...]
    created_by: UUID
    created_at: AwareDatetime


class ComparisonPage(Contract):
    items: tuple[ComparisonDTO, ...]
    offset: int
    limit: int
    total: int


class ConfigDiffOptions(Contract):
    pass


class ConfigDiffRequest(Contract):
    options: ConfigDiffOptions = Field(default_factory=ConfigDiffOptions)
