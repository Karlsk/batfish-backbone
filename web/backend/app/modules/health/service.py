from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from app.contracts.errors import ErrorCode, FieldError, ServiceError

from .schemas import DependencyStatus, HealthResponse


class HealthService:
    def __init__(
        self,
        *,
        read_statuses: Callable[[], Mapping[str, DependencyStatus]],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_age_seconds: float = 60,
    ):
        # The provider reads cached observations; requests never execute SDK work.
        self.read_statuses = read_statuses
        self.clock = clock
        self.max_age_seconds = max_age_seconds

    def live(self) -> HealthResponse:
        return HealthResponse(status="alive")

    def ready(self) -> HealthResponse:
        try:
            states = self.read_statuses()
        except Exception:
            raise ServiceError(ErrorCode.NOT_READY, retryable=True) from None
        now = self.clock()
        failures = []
        for name in ("database", "worker", "engine"):
            status = states.get(name)
            if (
                status is None
                or not status.available
                or status.checked_at is None
                or not 0 <= (now - status.checked_at).total_seconds() <= self.max_age_seconds
            ):
                failures.append(FieldError(path=("dependencies", name), message="Not ready"))
        if failures:
            raise ServiceError(ErrorCode.NOT_READY, field_errors=tuple(failures), retryable=True)
        return HealthResponse(status="ready")
