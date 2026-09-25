from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.contracts.dto import Actor, JobDTO
from app.modules.jobs.schemas import JobPage, JobStatus
from app.modules.jobs.service import JobsService


def create_router(service: JobsService, *, read_actor, write_actor):
    router = APIRouter(prefix="/jobs", tags=["Jobs"])

    @router.get("", response_model=JobPage)
    def list_jobs(
        status: JobStatus | None = None,
        network_id: UUID | None = None,
        created_by: UUID | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        actor: Actor = Depends(read_actor),
    ):
        return service.list(
            actor,
            status=status,
            network_id=network_id,
            created_by=created_by,
            offset=offset,
            limit=limit,
        )

    @router.get("/{job_id}", response_model=JobDTO)
    def get_job(job_id: UUID, actor: Actor = Depends(read_actor)):
        return service.get(actor, job_id)

    @router.post("/{job_id}/cancel", response_model=JobDTO)
    def cancel_job(job_id: UUID, actor: Actor = Depends(write_actor)):
        return service.cancel(actor, job_id)

    return router
