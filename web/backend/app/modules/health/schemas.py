from typing import Literal

from pydantic import AwareDatetime

from app.contracts.base import Contract


class HealthResponse(Contract):
    status: Literal["alive", "ready"]


class DependencyStatus(Contract):
    available: bool
    checked_at: AwareDatetime | None = None
