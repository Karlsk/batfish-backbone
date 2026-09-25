from collections.abc import Callable
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.contracts.dto import Actor
from app.contracts.errors import ServiceError
from app.infrastructure.http import error_response
from app.modules.networks.schemas import CreateNetworkRequest, NetworkDTO, NetworkPage
from app.modules.networks.service import NetworksService


def create_router(service: NetworksService, *, read_actor: Callable, write_actor: Callable):
    router = APIRouter(prefix="/networks", tags=["Networks"])

    @router.get("", response_model=NetworkPage)
    def list_networks(
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        actor: Actor = Depends(read_actor),
    ):
        return service.list(actor, offset=offset, limit=limit)

    @router.get("/{network_id}", response_model=NetworkDTO)
    def get_network(network_id: UUID, actor: Actor = Depends(read_actor)):
        return service.get(actor, network_id)

    @router.post("", status_code=201, response_model=NetworkDTO)
    def create_network(
        body: CreateNetworkRequest,
        request: Request,
        response: Response,
        idempotency_key: str | None = Header(
            None, min_length=1, max_length=128, pattern=r"^[!-~]+$"
        ),
        actor: Actor = Depends(write_actor),
    ):
        key = idempotency_key if idempotency_key is not None else uuid4().hex
        response.headers["Idempotency-Key"] = key
        try:
            return service.create(actor, body, idempotency_key=key)
        except ServiceError as error:
            return error_response(
                request.state.request_id,
                error.code,
                field_errors=error.field_errors,
                retryable=error.retryable,
                headers={"Idempotency-Key": key},
            )

    return router
