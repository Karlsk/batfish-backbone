from ipaddress import IPv4Address
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.contracts.base import Contract

Priority = Literal["high", "medium", "low"]
Protocol = Literal["icmp", "tcp", "udp", "gre", "esp", "ah", "ospf", "sctp", "ipinip"]
Name = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r".*\S.*")]
StartLocation = Annotated[
    str, StringConstraints(min_length=1, max_length=4096, pattern=r"^[^\x00-\x1f\x7f]+$")
]
Port = Annotated[StrictInt, Field(ge=0, le=65535)]


class ConcernFlow(Contract):
    start_location: StartLocation
    destination_ip: IPv4Address
    source_ip: IPv4Address | None = None
    protocol: Protocol | None = None
    destination_port: Port | None = None

    @field_validator("destination_ip", "source_ip", mode="before")
    @classmethod
    def address_string(cls, value):
        if value is not None and not isinstance(value, str):
            raise ValueError("Expected an IPv4 address string")
        return value

    @model_validator(mode="after")
    def port_requires_transport(self):
        if self.destination_port is not None and self.protocol not in {"tcp", "udp"}:
            raise ValueError("Destination port requires TCP or UDP")
        return self


class CreateConcernRequest(Contract):
    network_id: UUID
    name: Name
    description: str | None = Field(default=None, max_length=2000)
    priority: Priority
    flows: tuple[ConcernFlow, ...] = Field(min_length=1, max_length=10)


class PatchConcernRequest(Contract):
    expected_version: StrictInt = Field(ge=1)
    name: Name | None = None
    description: str | None = Field(default=None, max_length=2000)
    priority: Priority | None = None
    flows: tuple[ConcernFlow, ...] | None = Field(default=None, min_length=1, max_length=10)
    archived: StrictBool | None = None

    @model_validator(mode="after")
    def require_change(self):
        changed = self.model_fields_set - {"expected_version"}
        if not changed:
            raise ValueError("At least one field must change")
        if any(getattr(self, key) is None for key in changed - {"description"}):
            raise ValueError("Required fields cannot be cleared")
        return self


class ConcernDTO(Contract):
    id: UUID
    network_id: UUID
    name: str
    description: str | None
    priority: Priority
    flows: tuple[ConcernFlow, ...]
    version: int
    archived: bool
    created_by: UUID
    updated_by: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ConcernPage(Contract):
    items: tuple[ConcernDTO, ...]
    offset: int
    limit: int
    total: int
