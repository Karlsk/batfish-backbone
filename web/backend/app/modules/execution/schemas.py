from dataclasses import dataclass
from typing import Callable, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.contracts.base import Contract


@dataclass(frozen=True)
class Handler:
    execute: Callable
    retry: Callable | None = None


class ReconcileRequest(Contract):
    resolution: Literal["confirmed_idle", "restarted"]
    note: str = Field(min_length=5, max_length=1000)


class EngineStatus(Contract):
    state: Literal["idle", "busy", "unknown"]
    owner: str | None
    updated_at: AwareDatetime | None
    interrupted_jobs: tuple[UUID, ...] = ()
