from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.contracts.dto import Actor
from app.modules.users.schemas import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserDTO,
    UserPage,
)
from app.modules.users.service import UsersService


def create_router(
    service: UsersService, *, read_actor: Callable, write_actor: Callable
) -> APIRouter:
    router = APIRouter(prefix="/users", tags=["Users"])

    @router.get("", response_model=UserPage)
    def list_users(
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        actor: Actor = Depends(read_actor),
    ):
        return service.list(actor, offset=offset, limit=limit)

    @router.post("", status_code=201, response_model=UserDTO)
    def create_user(body: CreateUserRequest, request: Request, actor: Actor = Depends(write_actor)):
        return service.create(actor, body, request_id=UUID(request.state.request_id))

    @router.patch("/{user_id}", response_model=UserDTO)
    def update_user(
        user_id: UUID,
        body: UpdateUserRequest,
        request: Request,
        actor: Actor = Depends(write_actor),
    ):
        return service.update(actor, user_id, body, request_id=UUID(request.state.request_id))

    @router.post("/{user_id}/reset-password", status_code=204)
    def reset_password(
        user_id: UUID,
        body: ResetPasswordRequest,
        request: Request,
        actor: Actor = Depends(write_actor),
    ):
        service.reset_password(
            actor,
            user_id,
            body.temporary_password.get_secret_value(),
            request_id=UUID(request.state.request_id),
        )
        return Response(status_code=204)

    return router
