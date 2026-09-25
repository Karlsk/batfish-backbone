from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.contracts.dto import Actor, JobDTO
from app.modules.lifecycle.schemas import DeletionOutcome, ReconcileDeletion
from app.modules.lifecycle.service import ResourceLifecycleService


def create_router(service: ResourceLifecycleService, *, write_actor):
    router = APIRouter(tags=["Lifecycle"])

    @router.delete("/networks/{network_id}", response_model=JobDTO, status_code=202)
    def delete_network(network_id: UUID, request: Request, actor: Actor = Depends(write_actor)):
        return service.delete(actor, network_id, request_id=UUID(request.state.request_id))

    @router.delete(
        "/networks/{network_id}/snapshots/{snapshot_id}", response_model=JobDTO, status_code=202
    )
    def delete_snapshot(
        network_id: UUID, snapshot_id: UUID, request: Request, actor: Actor = Depends(write_actor)
    ):
        return service.delete(
            actor, network_id, snapshot_id, request_id=UUID(request.state.request_id)
        )

    @router.post("/admin/deletions/{job_id}/reconcile", response_model=DeletionOutcome)
    def reconcile(
        job_id: UUID, body: ReconcileDeletion, request: Request, actor: Actor = Depends(write_actor)
    ):
        return service.reconcile(
            actor, job_id, note=body.note, request_id=UUID(request.state.request_id)
        )

    return router
