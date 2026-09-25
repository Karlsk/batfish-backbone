from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.contracts.errors import ErrorEnvelope
from app.infrastructure.database import Database
from app.infrastructure.http import RequestContextMiddleware, install_error_handlers
from app.infrastructure.settings import Settings
from app.infrastructure.worker import WorkerRunner
from app.modules.analysis.api import create_router as create_analysis_router
from app.modules.analysis.controller import AnalysisController
from app.modules.analysis.registry import Registry
from app.modules.analysis.service import AnalysisService
from app.modules.auth.api import create_router as create_auth_router
from app.modules.auth.service import AuthService
from app.modules.execution.api import create_router as create_execution_router
from app.modules.execution.controller import ExecutionController
from app.modules.execution.schemas import Handler
from app.modules.execution.service import ExecutionService
from app.modules.health.api import create_router
from app.modules.health.schemas import DependencyStatus
from app.modules.health.service import HealthService
from app.modules.jobs.api import create_router as create_jobs_router
from app.modules.jobs.service import JobsService
from app.modules.lifecycle.api import create_router as create_lifecycle_router
from app.modules.lifecycle.service import ResourceLifecycleService
from app.modules.networks.api import create_router as create_networks_router
from app.modules.networks.controller import NetworkController
from app.modules.networks.service import NetworksService
from app.modules.results.api import create_router as create_results_router
from app.modules.results.service import ResultsService
from app.modules.snapshots.api import create_router as create_snapshots_router
from app.modules.snapshots.controller import SnapshotController
from app.modules.snapshots.service import SnapshotsService
from app.modules.uploads.api import create_router as create_uploads_router
from app.modules.uploads.service import UploadsService
from app.modules.users.api import create_router as create_users_router
from app.modules.users.service import UsersService


def database_metadata():
    """Composition is the only place registering models across module boundaries."""
    from app.infrastructure.database import Base
    from app.infrastructure.engine import EngineSlot  # noqa: F401
    from app.modules.audit import models as audit_models  # noqa: F401
    from app.modules.auth import models as auth_models  # noqa: F401
    from app.modules.execution import models as execution_models  # noqa: F401
    from app.modules.jobs import models as jobs_models  # noqa: F401
    from app.modules.networks import models as networks_models  # noqa: F401
    from app.modules.results import models as results_models  # noqa: F401
    from app.modules.snapshots import models as snapshots_models  # noqa: F401
    from app.modules.uploads import models as uploads_models  # noqa: F401
    from app.modules.users import models as users_models  # noqa: F401

    return Base.metadata


def create_app(
    settings: Settings | None = None,
    *,
    health_service: HealthService | None = None,
    database: Database | None = None,
) -> FastAPI:
    settings = settings if settings is not None else Settings()
    owns_database = database is None and settings.database_url is not None
    db = Database(settings.database_url) if owns_database else database

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            if owns_database:
                db.close()

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
        lifespan=lifespan,
        responses={422: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}},
    )
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(create_router(health), prefix="/api/v1")
    if db is not None:
        database_metadata()
        users = UsersService(db)
        auth = AuthService(db, users, settings)
        app.state.auth_service = auth
        app.state.users_service = users

        def read_actor(request: Request):
            return auth.require_actor(request.cookies.get("batfish_session"))

        def write_actor(request: Request):
            return auth.require_write(
                request.cookies.get("batfish_session"),
                origin=request.headers.get("origin"),
                csrf_token=request.headers.get("x-csrf-token"),
            )

        app.include_router(
            create_auth_router(auth, secure_cookie=settings.auth_cookie_secure), prefix="/api/v1"
        )
        app.include_router(
            create_users_router(users, read_actor=read_actor, write_actor=write_actor),
            prefix="/api/v1",
        )
        jobs = JobsService(db, auth, settings)
        app.state.jobs_service = jobs
        app.include_router(
            create_jobs_router(jobs, read_actor=read_actor, write_actor=write_actor),
            prefix="/api/v1",
        )
        networks = NetworksService(db, auth, jobs, NetworkController(db, settings))
        app.state.networks_service = networks
        app.include_router(
            create_networks_router(networks, read_actor=read_actor, write_actor=write_actor),
            prefix="/api/v1",
        )
        uploads = UploadsService(db, auth, networks, settings)
        app.state.uploads_service = uploads
        app.include_router(
            create_uploads_router(uploads, read_actor=read_actor, write_actor=write_actor),
            prefix="/api/v1",
        )
        snapshots = SnapshotsService(
            db, auth, networks, uploads, jobs, SnapshotController(db, settings)
        )
        app.state.snapshots_service = snapshots
        app.include_router(
            create_snapshots_router(snapshots, read_actor=read_actor, write_actor=write_actor),
            prefix="/api/v1",
        )
        results = ResultsService(db, auth, settings)
        app.state.results_service = results
        app.include_router(create_results_router(results, read_actor=read_actor), prefix="/api/v1")
        analysis = AnalysisService(
            auth, snapshots, jobs, results, AnalysisController(db, settings), Registry()
        )
        app.state.analysis_service = analysis
        app.include_router(
            create_analysis_router(analysis, read_actor=read_actor, write_actor=write_actor),
            prefix="/api/v1",
        )
        lifecycle = ResourceLifecycleService(auth, jobs, networks, snapshots)
        app.state.lifecycle_service = lifecycle
        app.include_router(
            create_lifecycle_router(lifecycle, write_actor=write_actor), prefix="/api/v1"
        )
        execution = ExecutionService(
            db,
            auth,
            jobs,
            handlers={
                "deletion": Handler(lifecycle.execute),
                "initialization": Handler(snapshots.execute, snapshots.retry),
                "analysis": Handler(analysis.execute, analysis.retry, analysis.publish),
            },
            controller=ExecutionController(db, settings),
            settings=settings,
        )
        app.state.execution_service = execution
        app.include_router(
            create_execution_router(execution, read_actor=read_actor, write_actor=write_actor),
            prefix="/api/v1",
        )
        if health_service is None:
            health.read_statuses = lambda: {
                name: DependencyStatus(**value) for name, value in execution.observations().items()
            }
    return app


def initialize_administrator(settings: Settings, username: str, password: str) -> None:
    database_metadata()
    database = Database(settings.database_url)
    try:
        UsersService(database).bootstrap_admin(username, password)
    finally:
        database.close()


def cleanup_uploads(settings: Settings) -> int:
    database_metadata()
    database = Database(settings.database_url)
    try:
        users = UsersService(database)
        auth = AuthService(database, users, settings)
        networks = NetworksService(
            database, auth, JobsService(), NetworkController(database, settings)
        )
        return UploadsService(database, auth, networks, settings).cleanup_expired()
    finally:
        database.close()


def create_worker(settings: Settings, *, database=None, handlers=None):
    database_metadata()
    db = database if database is not None else Database(settings.database_url)
    auth = AuthService(db, UsersService(db), settings)
    jobs = JobsService(db, auth, settings)
    networks = NetworksService(db, auth, jobs, NetworkController(db, settings))
    uploads = UploadsService(db, auth, networks, settings)
    snapshots = SnapshotsService(
        db, auth, networks, uploads, jobs, SnapshotController(db, settings)
    )
    results = ResultsService(db, auth, settings)
    analysis = AnalysisService(
        auth, snapshots, jobs, results, AnalysisController(db, settings), Registry()
    )
    lifecycle = ResourceLifecycleService(auth, jobs, networks, snapshots)
    registered = {
        "deletion": Handler(lifecycle.execute),
        "initialization": Handler(snapshots.execute, snapshots.retry),
        "analysis": Handler(analysis.execute, analysis.retry, analysis.publish),
    }
    registered.update(handlers or {})
    execution = ExecutionService(
        db,
        auth,
        jobs,
        handlers=registered,
        controller=ExecutionController(db, settings),
        settings=settings,
    )
    return WorkerRunner(db, execution, settings)
