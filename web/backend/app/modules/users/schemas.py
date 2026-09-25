from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class UserRecord:
    """Internal repository value; credentials never enter an API response."""

    id: UUID
    username: str
    role: Literal["admin", "member"]
    enabled: bool
    must_change_password: bool
    password_hash: str = field(repr=False)
