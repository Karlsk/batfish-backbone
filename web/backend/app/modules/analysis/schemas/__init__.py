from collections.abc import Mapping
from dataclasses import dataclass
from typing import Callable, Literal
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from app.contracts.base import Contract
from app.contracts.dto import AnalysisContext
from app.contracts.results import StructuredAnswer


class EmptyOptions(Contract):
    pass


class BaseAnalysisRequest(Contract):
    options: EmptyOptions = Field(default_factory=EmptyOptions)


class Capability(Contract):
    id: str
    label: str
    stage: int
    enabled: bool
    disabled_reason: str | None
    required_fields: tuple[str, ...]
    options_schema: Mapping[str, JsonValue]
    defaults: Mapping[str, JsonValue]
    result_kind: Literal["table", "traces", "graph"]
    requires_dataplane: bool
    schema_version: str


@dataclass(frozen=True)
class Entry:
    id: str
    label: str
    request_model: type[BaseModel] = BaseAnalysisRequest
    enabled: bool = False
    disabled_reason: str | None = "Not implemented in this milestone"
    stage: int = 1
    result_kind: str = "table"
    requires_dataplane: bool = False
    schema_version: str = "1"
    question_id: str | None = None
    to_sdk: Callable = lambda request: {}


@dataclass(frozen=True)
class PreparedAnalysis:
    context: AnalysisContext
    parameters: dict
    cache_key: str
    quality: dict
    answer: StructuredAnswer | None = None
    cached_result_id: UUID | None = None
