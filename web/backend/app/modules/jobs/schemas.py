from collections.abc import Mapping
from typing import Literal

from pydantic import JsonValue, field_validator

from app.contracts.base import Contract, thaw
from app.contracts.dto import AnalysisContext, ExecutionContext, JobDTO

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]
TRANSITIONS = {
    "queued": frozenset({"running", "cancelled"}),
    "running": frozenset({"succeeded", "failed", "interrupted"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "interrupted": frozenset(),
}


class JobInput(Contract):
    kind: Literal["upload", "initialization", "analysis", "deletion"]
    context: ExecutionContext
    requested_parameters: Mapping[str, JsonValue]
    effective_parameters: Mapping[str, JsonValue]

    @field_validator("context", mode="before")
    @classmethod
    def accept_analysis_context(cls, value):
        return value.model_dump() if isinstance(value, AnalysisContext) else value

    @field_validator("requested_parameters", "effective_parameters", mode="before")
    @classmethod
    def accept_saved_parameters(cls, value):
        return thaw(value)


class JobPage(Contract):
    items: tuple[JobDTO, ...]
    offset: int
    limit: int
    total: int
