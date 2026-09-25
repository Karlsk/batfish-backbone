from enum import StrEnum

from .base import Contract


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONFLICT = "CONFLICT"
    NOT_READY = "NOT_READY"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    ENGINE_STATE_UNKNOWN = "ENGINE_STATE_UNKNOWN"


class FieldError(Contract):
    path: tuple[str | int, ...]
    message: str


class ErrorDetail(Contract):
    code: ErrorCode
    message: str
    field_errors: tuple[FieldError, ...] = ()
    request_id: str
    retryable: bool = False


class ErrorEnvelope(Contract):
    error: ErrorDetail


class ServiceError(Exception):
    """Business failure identified by a safe code; no HTTP or SDK dependency."""

    def __init__(
        self, code: ErrorCode, *, field_errors: tuple[FieldError, ...] = (), retryable: bool = False
    ):
        super().__init__(code.value)
        self.code = code
        self.field_errors = field_errors
        self.retryable = retryable
