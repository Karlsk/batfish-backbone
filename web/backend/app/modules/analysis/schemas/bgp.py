from typing import Literal

from pydantic import Field

from app.contracts.base import Contract
from app.modules.analysis.schemas.inventory import Selector


class BgpOptions(Contract):
    mode: Literal["status", "compatibility"] = "status"
    nodes: Selector | None = None
    remote_nodes: Selector | None = None


class BgpRequest(Contract):
    options: BgpOptions = Field(default_factory=BgpOptions)
