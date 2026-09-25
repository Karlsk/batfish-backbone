from uuid import UUID

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.multipart import bounded_form
from app.modules.uploads.schemas import UploadDTO, UploadInput
from app.modules.uploads.service import UploadsService

MULTIPART_SCHEMA = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "oneOf": [
                        {
                            "type": "object",
                            "required": ["files"],
                            "properties": {
                                "files": {
                                    "type": "array",
                                    "items": {"type": "string", "format": "binary"},
                                }
                            },
                            "additionalProperties": False,
                        },
                        {
                            "type": "object",
                            "required": ["archive"],
                            "properties": {"archive": {"type": "string", "format": "binary"}},
                            "additionalProperties": False,
                        },
                    ]
                }
            }
        },
    }
}


def create_router(service: UploadsService, *, write_actor):
    router = APIRouter(tags=["uploads"])

    @router.post(
        "/networks/{network_id}/uploads",
        status_code=201,
        response_model=UploadDTO,
        openapi_extra=MULTIPART_SCHEMA,
    )
    async def create(network_id: UUID, request: Request, actor=Depends(write_actor)):
        async with bounded_form(
            request, max_bytes=service.limits.max_bytes, max_files=service.limits.max_files
        ) as form:
            items = form.multi_items()
            keys = {key for key, _ in items}
            if (
                keys not in ({"files"}, {"archive"})
                or keys == {"archive"}
                and len(items) != 1
                or any(not isinstance(value, UploadFile) for _, value in items)
            ):
                raise ServiceError(ErrorCode.VALIDATION_ERROR)
            inputs = [UploadInput(file.filename or "", file.file) for _, file in items]
            return await run_in_threadpool(
                service.create, actor, network_id, inputs, archive=keys == {"archive"}
            )

    return router
