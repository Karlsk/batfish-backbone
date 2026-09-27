from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.business_concerns.models import BusinessConcern, BusinessConcernVersion
from app.modules.business_concerns.schemas import ConcernDTO


def _dto(row: BusinessConcern | BusinessConcernVersion) -> ConcernDTO:
    values = {name: getattr(row, name) for name in ConcernDTO.model_fields if name != "id"}
    values["id"] = row.id if isinstance(row, BusinessConcern) else row.concern_id
    return ConcernDTO.model_validate(values)


def _historical(row: BusinessConcern) -> BusinessConcernVersion:
    return BusinessConcernVersion(
        concern_id=row.id,
        version=row.version,
        network_id=row.network_id,
        name=row.name,
        description=row.description,
        priority=row.priority,
        flows=row.flows,
        archived=row.archived,
        created_by=row.created_by,
        updated_by=row.updated_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class BusinessConcernsRepository:
    def __init__(self, transaction: Session):
        self._transaction = transaction

    def create(
        self,
        *,
        network_id: UUID,
        actor_id: UUID,
        name: str,
        description: str | None,
        priority: str,
        flows: list[dict],
    ) -> ConcernDTO:
        now = datetime.now(UTC)
        row = BusinessConcern(
            id=uuid4(),
            network_id=network_id,
            name=name,
            description=description,
            priority=priority,
            flows=flows,
            version=1,
            archived=False,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._transaction.add(row)
        self._transaction.flush()
        self._transaction.add(_historical(row))
        self._transaction.flush()
        return _dto(row)

    def get(
        self, identifier: UUID, *, version: int | None = None, lock: bool = False
    ) -> ConcernDTO | None:
        if version is not None:
            row = self._transaction.get(BusinessConcernVersion, (identifier, version))
        else:
            row = self._transaction.scalar(
                select(BusinessConcern).where(BusinessConcern.id == identifier).with_for_update()
                if lock
                else select(BusinessConcern).where(BusinessConcern.id == identifier)
            )
        return _dto(row) if row is not None else None

    def list(
        self, *, network_id: UUID | None, include_archived: bool, offset: int, limit: int
    ) -> tuple[list[ConcernDTO], int]:
        conditions = []
        if network_id is not None:
            conditions.append(BusinessConcern.network_id == network_id)
        if not include_archived:
            conditions.append(BusinessConcern.archived.is_(False))
        rows = self._transaction.scalars(
            select(BusinessConcern)
            .where(*conditions)
            .order_by(BusinessConcern.created_at, BusinessConcern.id)
            .offset(offset)
            .limit(limit)
        )
        total = self._transaction.scalar(
            select(func.count()).select_from(BusinessConcern).where(*conditions)
        )
        return [_dto(row) for row in rows], total or 0

    def active_counts(self, network_ids: tuple[UUID, ...]) -> dict[UUID, int]:
        if not network_ids:
            return {}
        rows = self._transaction.execute(
            select(BusinessConcern.network_id, func.count())
            .where(
                BusinessConcern.network_id.in_(network_ids),
                BusinessConcern.archived.is_(False),
            )
            .group_by(BusinessConcern.network_id)
        )
        return {network_id: count for network_id, count in rows}

    def update(
        self,
        identifier: UUID,
        *,
        actor_id: UUID,
        name: str,
        description: str | None,
        priority: str,
        flows: list[dict],
        archived: bool,
    ) -> ConcernDTO:
        row = self._transaction.get(BusinessConcern, identifier, with_for_update=True)
        row.name = name
        row.description = description
        row.priority = priority
        row.flows = flows
        row.archived = archived
        row.version += 1
        row.updated_by = actor_id
        row.updated_at = datetime.now(UTC)
        self._transaction.add(_historical(row))
        self._transaction.flush()
        return _dto(row)
