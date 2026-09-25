from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, SecretStr, model_validator

from app.contracts.base import Contract


@dataclass(frozen=True)
class UserRecord:
    """Internal repository value; credentials never enter an API response."""

    id: UUID
    username: str
    role: Literal["admin", "member"]
    enabled: bool
    must_change_password: bool
    password_hash: str = field(repr=False)
    created_at: datetime
    session_version: int = 0


class UserIdentity(Contract):
    user_id: UUID
    username: str
    role: Literal["admin", "member"]
    enabled: bool
    must_change_password: bool
    session_version: int


class UserDTO(Contract):
    id: UUID
    username: str
    role: Literal["admin", "member"]
    enabled: bool
    must_change_password: bool
    created_at: AwareDatetime


class CreateUserRequest(Contract):
    username: str = Field(min_length=1, max_length=128)
    temporary_password: SecretStr = Field(min_length=12, max_length=128)
    role: Literal["admin", "member"] = "member"


class UpdateUserRequest(Contract):
    enabled: bool | None = Field(default=None, strict=True)
    role: Literal["admin", "member"] | None = None

    @model_validator(mode="after")
    def nonempty_update(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Provide enabled or role, without null values")
        return self


class ResetPasswordRequest(Contract):
    temporary_password: SecretStr = Field(min_length=12, max_length=128)


class UserPage(Contract):
    items: tuple[UserDTO, ...]
    offset: int
    limit: int
    total: int
