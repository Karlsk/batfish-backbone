from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.contracts.dto import Actor
from app.modules.business_concerns.schemas import (
    ConcernDTO,
    ConcernPage,
    CreateConcernRequest,
    PatchConcernRequest,
)
from app.modules.business_concerns.service import BusinessConcernsService


def create_router(service: BusinessConcernsService, *, read_actor: Callable, write_actor: Callable):
    router = APIRouter(prefix="/business-concerns", tags=["Business concerns"])

    @router.get("", response_model=ConcernPage)
    def list_concerns(
        network_id: UUID | None = None,
        include_archived: bool = False,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        actor: Actor = Depends(read_actor),
    ):
        return service.list(
            actor,
            network_id=network_id,
            include_archived=include_archived,
            offset=offset,
            limit=limit,
        )

    @router.get("/{concern_id}", response_model=ConcernDTO)
    def get_concern(
        concern_id: UUID,
        version: int | None = Query(None, ge=1),
        actor: Actor = Depends(read_actor),
    ):
        return service.get(actor, concern_id, version=version)

    @router.post("", status_code=201, response_model=ConcernDTO)
    def create_concern(
        body: CreateConcernRequest, request: Request, actor: Actor = Depends(write_actor)
    ):
        return service.create(actor, body, request_id=UUID(request.state.request_id))

    @router.patch("/{concern_id}", response_model=ConcernDTO)
    def update_concern(
        concern_id: UUID,
        body: PatchConcernRequest,
        request: Request,
        actor: Actor = Depends(write_actor),
    ):
        return service.update(actor, concern_id, body, request_id=UUID(request.state.request_id))

    return router
