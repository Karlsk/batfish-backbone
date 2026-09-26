from ipaddress import IPv4Address, IPv4Network
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    Field,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.contracts.base import Contract


class InterfaceTarget(Contract):
    node: str = Field(min_length=1, max_length=255, pattern=r".*\S.*")
    interface: str = Field(min_length=1, max_length=255, pattern=r".*\S.*")


class FaultScenarioRequest(Contract):
    display_name: str = Field(min_length=1, max_length=255, pattern=r".*\S.*")
    deactivate_nodes: tuple[str, ...] = Field(default=(), max_length=100)
    deactivate_interfaces: tuple[InterfaceTarget, ...] = Field(default=(), max_length=500)

    @model_validator(mode="after")
    def require_targets(self):
        if not self.deactivate_nodes and not self.deactivate_interfaces:
            raise ValueError("At least one node or interface is required")
        if any(not name.strip() or len(name) > 255 for name in self.deactivate_nodes):
            raise ValueError("Node names must be nonempty and at most 255 characters")
        if len(set(self.deactivate_nodes)) != len(self.deactivate_nodes):
            raise ValueError("Duplicate nodes are not allowed")
        if len({(item.node, item.interface) for item in self.deactivate_interfaces}) != len(
            self.deactivate_interfaces
        ):
            raise ValueError("Duplicate interfaces are not allowed")
        return self


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


IpProtocol = Literal["icmp", "tcp", "udp", "gre", "esp", "ah", "ospf", "sctp", "ipinip"]


def ipv4_space(value):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("Expected explicit IPv4 addresses or prefixes")
    parts = [part.strip() for part in value.split(",")]
    if not 1 <= len(parts) <= 16 or any(not part for part in parts):
        raise ValueError("Expected 1 to 16 IPv4 addresses or prefixes")
    parsed = []
    for part in parts:
        try:
            item = IPv4Network(part, strict=True) if "/" in part else IPv4Address(part)
        except ValueError:
            raise ValueError("Expected canonical IPv4 addresses or prefixes") from None
        if str(item) != part:
            raise ValueError("Expected canonical IPv4 addresses or prefixes")
        if isinstance(item, IPv4Network) and item.prefixlen == 0:
            raise ValueError("Unbounded IPv4 scope is not allowed")
        parsed.append(part)
    return ",".join(parsed)


class ReachabilityDiffOptions(Contract):
    source_ips: str | None = None
    ip_protocols: tuple[IpProtocol, ...] = Field(default=("icmp",), min_length=1, max_length=9)
    destination_ports: tuple[StrictInt, ...] | None = Field(
        default=None, min_length=1, max_length=100
    )
    max_traces: StrictInt = Field(default=5, ge=1, le=20)

    @field_validator("source_ips", mode="before")
    @classmethod
    def source_space(cls, value):
        return None if value is None else ipv4_space(value)

    @field_validator("destination_ports")
    @classmethod
    def ports(cls, value):
        if value is not None and any(port < 0 or port > 65535 for port in value):
            raise ValueError("Ports must be between 0 and 65535")
        return value

    @model_validator(mode="after")
    def ports_require_transport(self):
        if self.destination_ports and not set(self.ip_protocols) <= {"tcp", "udp"}:
            raise ValueError("Destination ports require only TCP/UDP protocols")
        return self


class ReachabilityDiffRequest(Contract):
    destination_ips: str
    start_location: Annotated[
        str, StringConstraints(min_length=1, max_length=4096, pattern=r"^[^\x00-\x1f\x7f]+$")
    ]
    options: ReachabilityDiffOptions = Field(default_factory=ReachabilityDiffOptions)

    @field_validator("destination_ips", mode="before")
    @classmethod
    def destination_space(cls, value):
        return ipv4_space(value)
