from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.contracts.dto import Actor
from app.modules.changes.schemas import ComparisonDTO, ComparisonPage, CreateComparisonRequest
from app.modules.changes.service import ChangesService


def create_router(service: ChangesService, *, read_actor, write_actor):
    router = APIRouter(tags=["Changes"])

    @router.post(
        "/networks/{network_id}/comparisons", response_model=ComparisonDTO, status_code=201
    )
    def create(
        network_id: UUID,
        body: CreateComparisonRequest,
        request: Request,
        actor: Actor = Depends(write_actor),
    ):
        return service.create(actor, network_id, body, request_id=UUID(request.state.request_id))

    @router.get("/networks/{network_id}/comparisons", response_model=ComparisonPage)
    def list_comparisons(
        network_id: UUID,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        actor: Actor = Depends(read_actor),
    ):
        return service.list(actor, network_id, offset=offset, limit=limit)

    @router.get("/comparisons/{comparison_id}", response_model=ComparisonDTO)
    def get(comparison_id: UUID, actor: Actor = Depends(read_actor)):
        return service.get(actor, comparison_id)

    @router.delete("/comparisons/{comparison_id}", status_code=204)
    def delete(comparison_id: UUID, request: Request, actor: Actor = Depends(write_actor)):
        service.delete(actor, comparison_id, request_id=UUID(request.state.request_id))

    return router
