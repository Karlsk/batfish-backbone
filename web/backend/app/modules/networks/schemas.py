from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator

from app.contracts.base import Contract


class CreateNetworkRequest(Contract):
    display_name: str = Field(min_length=1, max_length=255)

    @field_validator("display_name")
    @classmethod
    def meaningful_label(cls, value):
        if not value.strip():
            raise ValueError("Display name cannot be blank")
        return value


class NetworkDTO(Contract):
    id: UUID
    display_name: str
    engine_name: str
    sync_state: Literal["pending", "ready", "failed", "deleting", "deleted"]
    sync_error: str | None = None
    created_by: UUID
    created_at: AwareDatetime


class NetworkPage(Contract):
    items: tuple[NetworkDTO, ...]
    offset: int
    limit: int
    total: int


class NetworkUnavailable(RuntimeError):
    def __init__(self, reason: str, *, failed: bool = False):
        self.reason = reason
        self.failed = failed
        super().__init__(reason)
