from typing import Literal
from uuid import UUID

from pydantic import Field

from app.contracts.base import Contract


class ReconcileDeletion(Contract):
    note: str = Field(min_length=10, max_length=1000, pattern=r".*\S.*")


class DeletionOutcome(Contract):
    resource_id: UUID
    state: Literal["ready", "ready_with_warnings", "failed", "deleted"]
