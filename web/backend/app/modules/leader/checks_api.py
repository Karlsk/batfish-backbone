from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from app.contracts.dto import Actor
from app.modules.leader.checks_schemas import (
    CheckRun,
    CheckRunPage,
    CheckTemplatePage,
    CreateCheckRunRequest,
)
from app.modules.leader.checks_service import CheckRunsService


def create_router(service: CheckRunsService, *, read_actor: Callable, write_actor: Callable):
    router = APIRouter(prefix="/leader", tags=["Leader checks"])

    @router.get("/check-templates", response_model=CheckTemplatePage)
    def templates(actor: Actor = Depends(read_actor)):
        return service.templates(actor)

    @router.get("/check-runs", response_model=CheckRunPage)
    def list_runs(
        network_id: UUID | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        actor: Actor = Depends(read_actor),
    ):
        return service.list(actor, network_id=network_id, offset=offset, limit=limit)

    @router.get("/check-runs/{run_id}", response_model=CheckRun)
    def get_run(run_id: UUID, actor: Actor = Depends(read_actor)):
        return service.get(actor, run_id)

    @router.post("/check-runs", status_code=201, response_model=CheckRun)
    def create_run(
        body: CreateCheckRunRequest,
        request: Request,
        idempotency_key: str = Header(..., max_length=128),
        actor: Actor = Depends(write_actor),
    ):
        return service.create(
            actor,
            body,
            idempotency_key=idempotency_key,
            request_id=UUID(request.state.request_id),
        )

    return router
