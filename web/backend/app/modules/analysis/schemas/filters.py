from ipaddress import IPv4Address

from pydantic import Field, field_validator, model_validator

from app.contracts.base import Contract
from app.modules.analysis.schemas import EmptyOptions
from app.modules.analysis.schemas.inventory import Expression, Selector
from app.modules.analysis.schemas.traceroute import Port, Protocol


class FilterTestOptions(Contract):
    ip_protocols: tuple[Protocol, ...] = Field(default=("icmp",), min_length=1, max_length=9)
    source_ports: tuple[Port, ...] | None = Field(default=None, min_length=1, max_length=100)
    destination_ports: tuple[Port, ...] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def ports_require_transport(self):
        if (self.source_ports or self.destination_ports) and not set(self.ip_protocols) <= {
            "tcp",
            "udp",
        }:
            raise ValueError("Ports require only TCP/UDP protocols")
        return self


class FilterTestRequest(Contract):
    source_ip: IPv4Address
    destination_ip: IPv4Address
    filters: Selector
    nodes: Selector | None = None
    options: FilterTestOptions = Field(default_factory=FilterTestOptions)

    @field_validator("source_ip", "destination_ip", mode="before")
    @classmethod
    def address_string(cls, value):
        if not isinstance(value, str):
            raise ValueError("Expected an IPv4 address string")
        return value


class ResolveFiltersRequest(Contract):
    nodes: Selector | None = None
    filter_expression: Expression | None = None
    options: EmptyOptions = Field(default_factory=EmptyOptions)
