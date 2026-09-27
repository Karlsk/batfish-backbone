from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from app.contracts.dto import Actor
from app.modules.leader.briefings_schemas import (
    Briefing,
    BriefingPage,
    CreateBriefingRequest,
    ReviseBriefingRequest,
)
from app.modules.leader.briefings_service import BriefingsService


def create_router(service: BriefingsService, *, read_actor: Callable, write_actor: Callable):
    router = APIRouter(prefix="/leader/briefings", tags=["Leader briefings"])

    @router.get("", response_model=BriefingPage)
    def list_briefings(
        network_id: UUID | None = None,
        include_archived: bool = False,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        actor: Actor = Depends(read_actor),
    ):
        return service.list(
            actor,
            network_id=network_id,
            include_archived=include_archived,
            offset=offset,
            limit=limit,
        )

    @router.get("/{briefing_id}", response_model=Briefing)
    def get_briefing(briefing_id: UUID, actor: Actor = Depends(read_actor)):
        return service.get(actor, briefing_id)

    @router.post("", status_code=201, response_model=Briefing)
    def create_briefing(
        body: CreateBriefingRequest,
        request: Request,
        idempotency_key: str = Header(..., min_length=1, max_length=128),
        actor: Actor = Depends(write_actor),
    ):
        return service.create(
            actor,
            body,
            idempotency_key=idempotency_key,
            request_id=UUID(request.state.request_id),
        )

    @router.patch("/{briefing_id}", response_model=Briefing)
    def revise_briefing(
        briefing_id: UUID,
        body: ReviseBriefingRequest,
        request: Request,
        idempotency_key: str = Header(..., min_length=1, max_length=128),
        actor: Actor = Depends(write_actor),
    ):
        return service.revise(
            actor,
            briefing_id,
            body,
            idempotency_key=idempotency_key,
            request_id=UUID(request.state.request_id),
        )

    @router.post("/{briefing_id}/archive", response_model=Briefing)
    def archive_briefing(briefing_id: UUID, request: Request, actor: Actor = Depends(write_actor)):
        return service.archive(actor, briefing_id, request_id=UUID(request.state.request_id))

    return router
