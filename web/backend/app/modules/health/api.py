from fastapi import APIRouter

from app.contracts.errors import ErrorEnvelope

from .schemas import HealthResponse
from .service import HealthService


def create_router(service: HealthService) -> APIRouter:
    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("/live", response_model=HealthResponse)
    def live() -> HealthResponse:
        return service.live()

    @router.get("/ready", response_model=HealthResponse, responses={503: {"model": ErrorEnvelope}})
    def ready() -> HealthResponse:
        return service.ready()

    return router
