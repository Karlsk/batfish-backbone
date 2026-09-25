from ipaddress import IPv4Address
from typing import Annotated, Literal

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.contracts.base import Contract

Port = Annotated[StrictInt, Field(ge=0, le=65535)]
Protocol = Literal["icmp", "tcp", "udp", "gre", "esp", "ah", "ospf", "sctp", "ipinip"]


class TraceOptions(Contract):
    source_ip: IPv4Address | None = None
    ip_protocols: tuple[Protocol, ...] = Field(default=("icmp",), min_length=1, max_length=9)
    source_ports: tuple[Port, ...] | None = Field(default=None, min_length=1, max_length=100)
    destination_ports: tuple[Port, ...] | None = Field(default=None, min_length=1, max_length=100)
    max_traces: StrictInt = Field(default=5, ge=1, le=20)
    ignore_filters: StrictBool = False

    @field_validator("source_ip", mode="before")
    @classmethod
    def source_string(cls, value):
        if value is not None and not isinstance(value, str):
            raise ValueError("Expected an IPv4 address string")
        return value

    @model_validator(mode="after")
    def ports_require_transport(self):
        if (self.source_ports or self.destination_ports) and not set(self.ip_protocols) <= {
            "tcp",
            "udp",
        }:
            raise ValueError("Ports require only TCP/UDP protocols")
        return self


class TraceRequest(Contract):
    start_location: Annotated[
        str, StringConstraints(min_length=1, max_length=4096, pattern=r"^[^\x00-\x1f\x7f]+$")
    ]
    destination_ip: IPv4Address
    options: TraceOptions = Field(default_factory=TraceOptions)

    @field_validator("destination_ip", mode="before")
    @classmethod
    def destination_string(cls, value):
        if not isinstance(value, str):
            raise ValueError("Expected an IPv4 address string")
        return value
