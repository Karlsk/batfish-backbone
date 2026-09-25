from fastapi import FastAPI

from app.contracts.errors import ErrorEnvelope
from app.infrastructure.http import RequestContextMiddleware, install_error_handlers
from app.infrastructure.settings import Settings
from app.modules.health.api import create_router
from app.modules.health.service import HealthService


def database_metadata():
    """Composition is the only place registering models across module boundaries."""
    from app.infrastructure.database import Base
    from app.modules.audit import models as audit_models  # noqa: F401
    from app.modules.auth import models as auth_models  # noqa: F401
    from app.modules.jobs import models as jobs_models  # noqa: F401
    from app.modules.networks import models as networks_models  # noqa: F401
    from app.modules.results import models as results_models  # noqa: F401
    from app.modules.snapshots import models as snapshots_models  # noqa: F401
    from app.modules.uploads import models as uploads_models  # noqa: F401
    from app.modules.users import models as users_models  # noqa: F401

    return Base.metadata


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
