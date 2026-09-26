"""The same typed routes request is used for a snapshot and a comparison."""

from ipaddress import IPv4Network
from typing import Literal

from pydantic import Field, field_validator

from app.contracts.base import Contract
from app.contracts.selection import Selector

Protocol = Literal[
    "all",
    "aggregate",
    "bgp",
    "connected",
    "ebgp",
    "eigrp",
    "eigrp-ext",
    "eigrp-int",
    "ibgp",
    "igp",
    "isis",
    "isis-l1",
    "isis-l2",
    "isis-el1",
    "isis-el2",
    "local",
    "ospf",
    "ospf-ext",
    "ospf-ext1",
    "ospf-ext2",
    "ospf-int",
    "ospf-inter",
    "ospf-intra",
    "rip",
    "static",
]


class RoutingOptions(Contract):
    vrfs: Selector | None = None
    network: IPv4Network | None = None
    protocols: tuple[Protocol, ...] | None = Field(default=None, min_length=1, max_length=30)
    prefix_match_type: Literal[
        "EXACT", "LONGEST_PREFIX_MATCH", "LONGER_PREFIXES", "SHORTER_PREFIXES"
    ] = "EXACT"
    rib: Literal["main", "bgp"] = "main"

    @field_validator("network", mode="before")
    @classmethod
    def network_string(cls, value):
        if value is not None:
            if not isinstance(value, str) or value != str(IPv4Network(value)):
                raise ValueError("Expected a canonical IPv4 CIDR prefix")
        return value


class RoutesRequest(Contract):
    nodes: Selector | None = None
    options: RoutingOptions = Field(default_factory=RoutingOptions)
