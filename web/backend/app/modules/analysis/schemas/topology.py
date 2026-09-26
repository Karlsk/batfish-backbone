from typing import Literal

from pydantic import Field

from app.contracts.base import Contract
from app.contracts.selection import Selector

TopologyView = Literal["layer3", "bgp", "ospf", "isis"]


class TopologyOptions(Contract):
    nodes: Selector | None = None
    remote_nodes: Selector | None = None


class TopologyRequest(Contract):
    view: TopologyView = "layer3"
    options: TopologyOptions = Field(default_factory=TopologyOptions)
