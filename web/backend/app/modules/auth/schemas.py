from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr

from app.contracts.base import Contract


class LoginRequest(Contract):
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordRequest(Contract):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)


class SessionInfo(Contract):
    user_id: UUID
    username: str
    role: Literal["admin", "member"]
    csrf_token: str = Field(repr=False)
    must_change_password: bool


@dataclass(frozen=True)
class SessionRecord:
    user_id: UUID
    session_version: int
    expires_at: datetime
    revoked_at: datetime | None
    csrf_secret: str = field(repr=False)
