from collections.abc import Mapping
from typing import Literal

from pydantic import Field, JsonValue

from app.contracts.base import Contract


class Column(Contract):
    key: str
    label: str
    type: str


class GraphNode(Contract):
    id: str
    label: str
    properties: Mapping[str, JsonValue] = Field(default_factory=dict)


class GraphEdge(Contract):
    id: str
    source: str
    target: str
    source_interface: str | None = None
    target_interface: str | None = None
    edge_type: Literal["layer3", "bgp", "ospf", "isis"]
    properties: Mapping[str, JsonValue] = Field(default_factory=dict)


class GraphData(Contract):
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    edge_type: Literal["layer3", "bgp", "ospf", "isis"]
    source: str


class GraphDTO(GraphData):
    scope: Mapping[str, JsonValue]
    truncated: bool


class StructuredAnswer(Contract):
    kind: Literal["table", "traces", "graph"]
    columns: tuple[Column, ...] = ()
    rows: tuple[Mapping[str, JsonValue], ...] = ()
    graph: GraphData | None = None
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
    dispositions: Mapping[str, int] = Field(default_factory=dict)
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
