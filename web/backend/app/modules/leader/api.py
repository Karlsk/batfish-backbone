from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.contracts.dto import Actor
from app.modules.leader.schemas import NetworkOverview, OverviewPage
from app.modules.leader.service import LeaderService


def create_router(service: LeaderService, *, read_actor: Callable):
    router = APIRouter(prefix="/leader", tags=["Leader"])

    @router.get("/overview", response_model=OverviewPage)
    def overview(
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=200),
        actor: Actor = Depends(read_actor),
    ):
        return service.overview(actor, offset=offset, limit=limit)

    @router.get("/networks/{network_id}", response_model=NetworkOverview)
    def network_detail(network_id: UUID, actor: Actor = Depends(read_actor)):
        return service.network_detail(actor, network_id)

    return router
