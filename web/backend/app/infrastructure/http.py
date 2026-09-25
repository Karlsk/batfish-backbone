import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.contracts.errors import ErrorCode, ErrorDetail, ErrorEnvelope, FieldError, ServiceError

ERRORS = {
    ErrorCode.VALIDATION_ERROR: (422, "Invalid request parameters"),
    ErrorCode.UNAUTHORIZED: (401, "Authentication required"),
    ErrorCode.FORBIDDEN: (403, "Permission denied"),
    ErrorCode.NOT_FOUND: (404, "Resource not found"),
    ErrorCode.METHOD_NOT_ALLOWED: (405, "Method not allowed"),
    ErrorCode.CONFLICT: (409, "Resource state conflict"),
    ErrorCode.NOT_READY: (503, "Service dependencies are not ready"),
    ErrorCode.INTERNAL_ERROR: (500, "Internal server error"),
    ErrorCode.HTTP_ERROR: (400, "Request failed"),
    ErrorCode.RATE_LIMITED: (429, "Too many failed attempts; try again later"),
}
logger = logging.getLogger("batfish_web.http")


def error_response(
    request_id: str,
    code: ErrorCode,
    *,
    field_errors=(),
    retryable=False,
    status: int | None = None,
    headers: dict[str, str] | None = None,
):
    default_status, message = ERRORS[code]
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            field_errors=field_errors,
            request_id=request_id,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=status or default_status,
        content=envelope.model_dump(mode="json"),
        headers={**(headers or {}), "X-Request-ID": request_id},
    )


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = False

        async def send_with_id(message: Message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception as error:
            # Never log exception messages, request bodies, credentials or configuration.
            logger.error(
                "Unhandled request failure request_id=%s exception_type=%s",
                request_id,
                type(error).__name__,
            )
            if started:
                # The status/body cannot be replaced after a streaming response starts.
                raise RuntimeError("Response interrupted; consult the request ID") from None
            response = error_response(request_id, ErrorCode.INTERNAL_ERROR)
            await response(scope, receive, send_with_id)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError):
        return error_response(
            request.state.request_id,
            error.code,
            field_errors=error.field_errors,
            retryable=error.retryable,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        fields = tuple(
            FieldError(
                path=tuple(e["loc"]),
                message="Required field" if e["type"] == "missing" else "Invalid value",
            )
            for e in error.errors()
        )
        # Pydantic's msg/input/ctx may contain secrets from the request or a validator.
        return error_response(
            request.state.request_id, ErrorCode.VALIDATION_ERROR, field_errors=fields
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        code = {
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            405: ErrorCode.METHOD_NOT_ALLOWED,
            409: ErrorCode.CONFLICT,
        }.get(error.status_code, ErrorCode.HTTP_ERROR)
        safe_headers = {
            k: v
            for k, v in (error.headers or {}).items()
            if k.lower() in {"allow", "www-authenticate", "retry-after"}
        }
        return error_response(
            request.state.request_id, code, status=error.status_code, headers=safe_headers
        )
