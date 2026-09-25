from collections.abc import Mapping
from typing import Literal

from pydantic import Field, JsonValue

from app.contracts.base import Contract


class Column(Contract):
    key: str
    label: str
    type: str


class StructuredAnswer(Contract):
    kind: Literal["table", "traces"]
    columns: tuple[Column, ...]
    rows: tuple[Mapping[str, JsonValue], ...]
    warnings: tuple[str, ...] = ()


class RowFilter(Contract):
    column: str
    op: Literal["eq", "contains"] = "eq"
    value: JsonValue


class TablePage(Contract):
    columns: tuple[Column, ...]
    rows: tuple[Mapping[str, JsonValue], ...]
    offset: int
    limit: int
    total: int
    truncated: bool


class TraceFlow(Contract):
    flow_id: str
    headers: Mapping[str, JsonValue]
    start_location: str | None
    trace_count: int = Field(ge=0)
    returned_trace_count: int = Field(ge=0)
    truncated: bool


class FlowPage(Contract):
    items: tuple[TraceFlow, ...]
    offset: int
    limit: int
    total: int
    truncated: bool


class TracePage(Contract):
    items: tuple[Mapping[str, JsonValue], ...]
    offset: int
    limit: int
    total: int
    trace_count: int
    truncated: bool
