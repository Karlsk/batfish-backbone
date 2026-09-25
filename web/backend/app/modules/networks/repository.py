from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.networks.models import Network
from app.modules.networks.schemas import NetworkDTO


def _dto(network: Network) -> NetworkDTO:
    return NetworkDTO.model_validate(
        {name: getattr(network, name) for name in NetworkDTO.model_fields}
    )


class NetworksRepository:
    def __init__(self, transaction: Session):
        self._transaction = transaction

    def add(self, *, network_id: UUID, display_name: str, actor_id: UUID) -> NetworkDTO:
        network = Network(
            id=network_id,
            display_name=display_name,
            engine_name="bfw-network-" + network_id.hex,
            created_by=actor_id,
        )
        self._transaction.add(network)
        self._transaction.flush()
        return _dto(network)

    def get(self, network_id: UUID) -> NetworkDTO | None:
        network = self._transaction.scalar(
            select(Network).where(Network.id == network_id, Network.deleted_at.is_(None))
        )
        return _dto(network) if network else None

    def list(self, *, offset: int, limit: int) -> tuple[list[NetworkDTO], int]:
        rows = self._transaction.scalars(
            select(Network)
            .where(Network.deleted_at.is_(None))
            .order_by(Network.created_at, Network.id)
            .offset(offset)
            .limit(limit)
        )
        total = self._transaction.scalar(
            select(func.count()).select_from(Network).where(Network.deleted_at.is_(None))
        )
        return [_dto(row) for row in rows], total

    def mark_ready(self, network_id: UUID) -> None:
        network = self._transaction.get(Network, network_id, with_for_update=True)
        network.sync_state, network.sync_error = "ready", None
        self._transaction.flush()

    def mark_problem(self, network_id: UUID, reason: str, *, failed: bool = False) -> None:
        network = self._transaction.get(Network, network_id, with_for_update=True)
        if network.sync_state != "ready":
            network.sync_error = reason
            if failed:
                network.sync_state = "failed"
            self._transaction.flush()
