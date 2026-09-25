from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ResourceReservation:
    resource_id: UUID
    created: bool
