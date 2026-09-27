from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, StringConstraints, model_validator

from app.contracts.base import Contract
from app.contracts.routing import Protocol
from app.contracts.selection import Selector
from app.modules.leader.checks_schemas import CheckTemplate, CheckTemplatePage

StartLocation = Annotated[
    str, StringConstraints(min_length=1, max_length=4096, pattern=r"^[^\x00-\x1f\x7f]+$")
]


class NoScope(Contract):
    pass


class NoOptions(Contract):
    pass


class NodeOptions(Contract):
    nodes: Selector | None = None
    properties: tuple[str, ...] | None = Field(default=None, min_length=1, max_length=100)


class InterfaceLeaderOptions(Contract):
    nodes: Selector | None = None
    interfaces: Selector | None = None
    properties: tuple[str, ...] | None = Field(default=None, min_length=1, max_length=100)


class LpmOptions(Contract):
    vrfs: Selector | None = None


FlowProtocol = Literal["icmp", "tcp", "udp", "gre", "esp", "ah", "ospf", "sctp", "ipinip"]
Port = Annotated[StrictInt, Field(ge=0, le=65535)]


class TraceOptions(Contract):
    source_ip: IPv4Address | None = None
    ip_protocols: tuple[FlowProtocol, ...] = Field(default=("icmp",), min_length=1, max_length=9)
    source_ports: tuple[Port, ...] | None = Field(default=None, min_length=1, max_length=100)
    destination_ports: tuple[Port, ...] | None = Field(default=None, min_length=1, max_length=100)
    max_traces: StrictInt = Field(default=5, ge=1, le=20)
    ignore_filters: StrictBool = False


class TopologyLeaderOptions(Contract):
    nodes: Selector | None = None
    remote_nodes: Selector | None = None
    view: Literal["layer3", "bgp", "ospf", "isis"] = "layer3"


class BgpOptions(Contract):
    mode: Literal["status", "compatibility"] = "status"
    nodes: Selector | None = None
    remote_nodes: Selector | None = None


class FilterTestOptions(Contract):
    ip_protocols: tuple[FlowProtocol, ...] = Field(default=("icmp",), min_length=1, max_length=9)
    source_ports: tuple[Port, ...] | None = Field(default=None, min_length=1, max_length=100)
    destination_ports: tuple[Port, ...] | None = Field(default=None, min_length=1, max_length=100)


class ReachabilityLeaderOptions(Contract):
    source_ips: str | None = Field(default=None, min_length=1, max_length=4096)
    ip_protocols: tuple[FlowProtocol, ...] = Field(default=("icmp",), min_length=1, max_length=9)
    destination_ports: tuple[Port, ...] | None = Field(default=None, min_length=1, max_length=100)
    max_traces: StrictInt = Field(default=5, ge=1, le=20)


class FaultInterfaceTarget(Contract):
    node: str = Field(min_length=1, max_length=255, pattern=r".*\S.*")
    interface: str = Field(min_length=1, max_length=255, pattern=r".*\S.*")


class FaultScope(Contract):
    display_name: str = Field(min_length=1, max_length=255, pattern=r".*\S.*")
    deactivate_nodes: tuple[str, ...] = Field(default=(), max_length=100)
    deactivate_interfaces: tuple[FaultInterfaceTarget, ...] = Field(default=(), max_length=500)

    @model_validator(mode="after")
    def require_targets(self):
        if not self.deactivate_nodes and not self.deactivate_interfaces:
            raise ValueError("At least one node or interface is required")
        return self


class RoutesScope(Contract):
    network: IPv4Network
    nodes: Selector | None = None


class LpmScope(Contract):
    ip: IPv4Address
    nodes: Selector | None = None


class TraceScope(Contract):
    start_location: StartLocation
    destination_ip: IPv4Address


class AclScope(Contract):
    source_ip: IPv4Address
    destination_ip: IPv4Address
    filters: Selector
    nodes: Selector | None = None


class ComparisonScope(Contract):
    comparison_id: UUID


class ChangeRoutesScope(ComparisonScope):
    network: IPv4Network
    nodes: Selector | None = None


class ChangeReachabilityScope(ComparisonScope):
    start_location: StartLocation
    destination_ips: str = Field(min_length=1, max_length=4096)


class RouteLeaderOptions(Contract):
    vrfs: Selector | None = None
    protocols: tuple[Protocol, ...] | None = Field(default=None, min_length=1, max_length=30)
    prefix_match_type: Literal[
        "EXACT", "LONGEST_PREFIX_MATCH", "LONGER_PREFIXES", "SHORTER_PREFIXES"
    ] = "EXACT"
    rib: Literal["main", "bgp"] = "main"


@dataclass(frozen=True)
class TemplateSpec:
    id: str
    title: str
    category: str
    capability: str | None
    scope_model: type[Contract]
    options_model: type[Contract]
    model_note: str
    version: str = "1"

    def public(self) -> CheckTemplate:
        scope_schema = self.scope_model.model_json_schema()
        return CheckTemplate(
            id=self.id,
            version=self.version,
            title=self.title,
            category=self.category,
            capability=self.capability,
            required_scope=tuple(scope_schema.get("required", ())),
            scope_schema=scope_schema,
            options_schema=self.options_model.model_json_schema(),
            model_note=self.model_note,
        )


MODEL_NOTE = "基于固定快照的 Batfish 配置模型；不代表在线设备状态。"
TEMPLATES = (
    TemplateSpec("configuration-quality", "配置质量", "mvp", None, NoScope, NoOptions, MODEL_NOTE),
    TemplateSpec("devices", "设备清单", "mvp", "nodes", NoScope, NodeOptions, MODEL_NOTE),
    TemplateSpec(
        "interfaces", "接口清单", "mvp", "interfaces", NoScope, InterfaceLeaderOptions, MODEL_NOTE
    ),
    TemplateSpec(
        "routes", "路由检查", "mvp", "routes", RoutesScope, RouteLeaderOptions, MODEL_NOTE
    ),
    TemplateSpec(
        "lpm-routes", "最长前缀匹配", "mvp", "lpm-routes", LpmScope, LpmOptions, MODEL_NOTE
    ),
    TemplateSpec(
        "traceroute",
        "虚拟连通性",
        "mvp",
        "traceroute",
        TraceScope,
        TraceOptions,
        "配置模型推演的单向路径，不证明实际转发或回程。",
    ),
    TemplateSpec(
        "topology", "网络拓扑", "advance", "topology", NoScope, TopologyLeaderOptions, MODEL_NOTE
    ),
    TemplateSpec("bgp", "BGP 会话", "advance", "bgp-sessions", NoScope, BgpOptions, MODEL_NOTE),
    TemplateSpec(
        "acl",
        "ACL 流量检查",
        "advance",
        "test-filters",
        AclScope,
        FilterTestOptions,
        "仅评估指定过滤器和流量，模型不支持的厂商需明确显示。",
    ),
    TemplateSpec(
        "change-config",
        "配置变更比较",
        "advance",
        "config-diff",
        ComparisonScope,
        NoOptions,
        "固定基线→候选方向；比较记录不等于差异分析结果。",
    ),
    TemplateSpec(
        "change-routes",
        "路由变更比较",
        "advance",
        "routes-diff",
        ChangeRoutesScope,
        RouteLeaderOptions,
        "仅解释明确前缀范围内的基线→候选差异。",
    ),
    TemplateSpec(
        "change-reachability",
        "可达性变更比较",
        "advance",
        "reachability-diff",
        ChangeReachabilityScope,
        ReachabilityLeaderOptions,
        "仅解释明确流量范围内的基线→候选差异。",
    ),
    TemplateSpec(
        "fault",
        "故障派生快照",
        "advance",
        "fault-scenario",
        FaultScope,
        NoOptions,
        "只停用显式选定的节点或接口；派生快照不是线上故障。",
    ),
)
BY_ID = {item.id: item for item in TEMPLATES}


def catalog() -> CheckTemplatePage:
    return CheckTemplatePage(items=tuple(item.public() for item in TEMPLATES))
