from fastapi import FastAPI

from app.contracts.errors import ErrorEnvelope
from app.infrastructure.http import RequestContextMiddleware, install_error_handlers
from app.infrastructure.settings import Settings
from app.modules.health.api import create_router
from app.modules.health.service import HealthService


def create_app(
    settings: Settings | None = None, *, health_service: HealthService | None = None
) -> FastAPI:
    settings = settings if settings is not None else Settings()
    health = (
        health_service
        if health_service is not None
        else HealthService(
            read_statuses=lambda: {}, max_age_seconds=settings.readiness_max_age_seconds
        )
    )
    app = FastAPI(
        title="Batfish Web API",
        version="0.1.0",
        debug=False,
        responses={422: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}},
    )
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(create_router(health), prefix="/api/v1")
    return app
