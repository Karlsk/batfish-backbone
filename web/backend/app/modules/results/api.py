from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import TypeAdapter, ValidationError

from app.contracts.dto import Actor, ResultEnvelope
from app.contracts.errors import ErrorCode, FieldError, ServiceError
from app.contracts.results import FlowPage, RowFilter, TablePage, TracePage
from app.modules.results.service import ResultsService


def create_router(service: ResultsService, *, read_actor):
    router = APIRouter(prefix="/results", tags=["Results"])

    @router.get("/{result_id}", response_model=ResultEnvelope)
    def get(result_id: UUID, actor: Actor = Depends(read_actor)):
        return service.get(actor, result_id)

    @router.get("/{result_id}/rows", response_model=TablePage)
    def rows(
        result_id: UUID,
        actor: Actor = Depends(read_actor),
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        sort: str | None = None,
        filters: str | None = Query(None, max_length=65536),
    ):
        try:
            parsed = (
                TypeAdapter(list[RowFilter]).validate_json(filters) if filters is not None else ()
            )
        except ValidationError as error:
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                field_errors=tuple(
                    FieldError(path=("query", "filters", *item["loc"]), message="Invalid value")
                    for item in error.errors()
                ),
            ) from None
        return service.rows(actor, result_id, offset=offset, limit=limit, sort=sort, filters=parsed)

    @router.get("/{result_id}/flows", response_model=FlowPage)
    def flows(
        result_id: UUID,
        actor: Actor = Depends(read_actor),
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ):
        return service.flows(actor, result_id, offset=offset, limit=limit)

    @router.get("/{result_id}/flows/{flow_id}/traces", response_model=TracePage)
    def traces(
        result_id: UUID,
        flow_id: str,
        actor: Actor = Depends(read_actor),
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ):
        return service.traces(actor, result_id, flow_id, offset=offset, limit=limit)

    return router
