from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response

from app.contracts.dto import Actor, JobDTO
from app.modules.execution.schemas import EngineStatus, ReconcileRequest
from app.modules.execution.service import ExecutionService


def create_router(service: ExecutionService, *, read_actor, write_actor):
    router = APIRouter(tags=["Execution"])

    @router.get("/admin/engine", response_model=EngineStatus)
    def state(actor: Actor = Depends(read_actor)):
        return service.engine_status(actor)

    @router.post("/admin/engine/reconcile", response_model=EngineStatus)
    def reconcile(body: ReconcileRequest, request: Request, actor: Actor = Depends(write_actor)):
        return service.reconcile(
            actor,
            resolution=body.resolution,
            note=body.note,
            request_id=UUID(request.state.request_id),
        )

    @router.post("/jobs/{job_id}/retry", response_model=JobDTO, status_code=202)
    def retry(
        job_id: UUID,
        response: Response,
        actor: Actor = Depends(write_actor),
        idempotency_key: str | None = Header(
            None, min_length=1, max_length=128, pattern=r"^[!-~]+$"
        ),
    ):
        key = idempotency_key or uuid4().hex
        response.headers["Idempotency-Key"] = key
        return service.retry(actor, job_id, idempotency_key=key)

    return router
