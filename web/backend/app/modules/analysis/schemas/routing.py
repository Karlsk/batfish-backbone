"""Routing request compatibility imports and LPM-specific schema."""

from ipaddress import IPv4Address

from pydantic import Field, field_validator

from app.contracts.base import Contract
from app.contracts.selection import Selector


class LpmOptions(Contract):
    vrfs: Selector | None = None


class LpmRequest(Contract):
    ip: IPv4Address
    nodes: Selector | None = None
    options: LpmOptions = Field(default_factory=LpmOptions)

    @field_validator("ip", mode="before")
    @classmethod
    def ip_string(cls, value):
        if not isinstance(value, str):
            raise ValueError("Expected an IPv4 address string")
        return value
