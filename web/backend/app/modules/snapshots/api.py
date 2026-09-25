from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.contracts.dto import Actor
from app.contracts.errors import ServiceError
from app.infrastructure.http import error_response
from app.modules.snapshots.schemas import (
    CreateSnapshotRequest,
    SnapshotCreated,
    SnapshotDTO,
    SnapshotPage,
)
from app.modules.snapshots.service import SnapshotsService


def create_router(service: SnapshotsService, *, read_actor, write_actor):
    router = APIRouter(prefix="/networks/{network_id}/snapshots", tags=["Snapshots"])

    @router.post("", response_model=SnapshotCreated, status_code=202)
    def create(
        network_id: UUID,
        body: CreateSnapshotRequest,
        request: Request,
        response: Response,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(
            None, min_length=1, max_length=128, pattern=r"^[!-~]+$"
        ),
    ):
        key = idempotency_key or uuid4().hex
        response.headers["Idempotency-Key"] = key
        try:
            return service.create(actor, network_id, body, idempotency_key=key)
        except ServiceError as error:
            return error_response(
                request.state.request_id,
                error.code,
                field_errors=error.field_errors,
                retryable=error.retryable,
                headers={"Idempotency-Key": key},
            )

    @router.get("", response_model=SnapshotPage)
    def list_snapshots(
        network_id: UUID,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        actor: Actor = Depends(read_actor),
    ):
        return service.list(actor, network_id, offset=offset, limit=limit)

    @router.get("/{snapshot_id}", response_model=SnapshotDTO)
    def get(network_id: UUID, snapshot_id: UUID, actor: Actor = Depends(read_actor)):
        return service.get(actor, network_id, snapshot_id)

    return router
