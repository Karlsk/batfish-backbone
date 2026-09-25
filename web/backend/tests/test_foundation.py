import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.contracts.dto import Actor, AnalysisContext, JobDTO, ResultEnvelope
from app.contracts.errors import ErrorCode, ServiceError
from app.infrastructure.settings import Settings
from app.main import create_app
from app.modules.health.schemas import DependencyStatus
from app.modules.health.service import HealthService


def test_live_without_batfish(monkeypatch):
    def unavailable(*args, **kwargs):
        raise AssertionError("Health request must not construct an SDK Session")

    monkeypatch.setattr("pybatfish.client.session.Session", unavailable)
    client = TestClient(create_app(Settings(batfish_host="unavailable.invalid")))
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    UUID(response.headers["x-request-id"])
    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 503
    assert ready.json()["error"]["code"] == "NOT_READY"


@pytest.mark.parametrize(
    "condition,expected",
    [
        ("healthy", 200),
        ("missing", 503),
        ("stale", 503),
        ("failed", 503),
        ("future", 503),
        ("exception", 503),
    ],
)
def test_readiness_requires_every_fresh_dependency(condition, expected):
    now = datetime.now(UTC)
    states = {
        name: DependencyStatus(available=True, checked_at=now)
        for name in ("database", "worker", "engine")
    }
    if condition == "missing":
        del states["engine"]
    elif condition == "stale":
        states["worker"] = DependencyStatus(available=True, checked_at=now - timedelta(seconds=61))
    elif condition == "failed":
        states["database"] = DependencyStatus(available=False, checked_at=now)
    elif condition == "future":
        states["engine"] = DependencyStatus(available=True, checked_at=now + timedelta(seconds=1))

    def read_statuses():
        if condition == "exception":
            raise RuntimeError("postgres://user:PRIVATE_PASSWORD@host/database")
        return states

    service = HealthService(read_statuses=read_statuses, clock=lambda: now, max_age_seconds=60)
    response = TestClient(create_app(health_service=service)).get("/api/v1/health/ready")
    assert response.status_code == expected
    assert "PRIVATE_PASSWORD" not in response.text
    if expected == 200:
        assert response.json() == {"status": "ready"}
    else:
        assert response.json()["error"]["retryable"] is True


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int

    @field_validator("limit")
    @classmethod
    def reject_seven(cls, value):
        if value == 7:
            raise ValueError("PRIVATE_VALIDATOR_CONTENT")
        return value


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    options: Options


def error_client():
    app = create_app()

    @app.post("/test-validation")
    def validate(payload: Payload):
        return payload

    @app.get("/test-unhandled")
    def unhandled():
        raise RuntimeError("PRIVATE_EXCEPTION_PASSWORD")

    @app.get("/test-http")
    def http_error():
        raise HTTPException(status_code=403, detail="PRIVATE_HTTP_DETAIL")

    @app.get("/test-service")
    def service_error():
        raise ServiceError(ErrorCode.CONFLICT)

    return TestClient(app)


@pytest.mark.parametrize(
    "payload",
    [
        {"options": {"limit": "PRIVATE_INPUT"}},
        {"options": {"limit": 7}},
        {"options": {"limit": 1, "unknown": "PRIVATE_INPUT"}},
    ],
)
def test_error_shape(payload, caplog):
    response = error_client().post("/test-validation", json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert set(error) == {"code", "message", "field_errors", "request_id", "retryable"}
    assert error["code"] == "VALIDATION_ERROR"
    assert error["request_id"] == response.headers["x-request-id"]
    assert error["field_errors"][0]["path"][:2] == ["body", "options"]
    assert "PRIVATE" not in response.text + caplog.text
    assert "input" not in error["field_errors"][0]


@pytest.mark.parametrize(
    "path,status,code",
    [
        ("/missing", 404, "NOT_FOUND"),
        ("/test-unhandled", 500, "INTERNAL_ERROR"),
        ("/test-http", 403, "FORBIDDEN"),
        ("/test-service", 409, "CONFLICT"),
    ],
)
def test_all_errors_are_sanitized_and_correlated(path, status, code, caplog):
    response = error_client().get(path, headers={"x-request-id": "untrusted-client-id"})
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["request_id"] == response.headers["x-request-id"]
    UUID(error["request_id"])
    assert error["request_id"] != "untrusted-client-id"
    assert "PRIVATE" not in response.text + caplog.text


def test_request_ids_are_unique_and_openapi_declares_errors():
    client = error_client()
    first = client.get("/api/v1/health/live")
    second = client.get("/api/v1/health/live")
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    assert client.post("/api/v1/health/live").json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    schema = client.get("/openapi.json").json()
    response = schema["paths"]["/api/v1/health/ready"]["get"]["responses"]["503"]
    assert response["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorEnvelope")


def test_settings_are_validated_without_disclosing_secrets(monkeypatch):
    monkeypatch.setenv("BATFISH_API_KEY", "PRIVATE_KEY")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:PRIVATE_DB@localhost/db")
    settings = Settings()
    assert settings.batfish_api_key.get_secret_value() == "PRIVATE_KEY"
    assert "PRIVATE" not in repr(settings) + settings.model_dump_json()
    assert settings.sdk_request_timeout == 120
    for values in ({"batfish_port": 0}, {"sdk_request_timeout": -1}, {"sdk_concurrency": 2}):
        with pytest.raises(ValidationError):
            Settings(**values)
    with pytest.raises(ValidationError) as failure:
        Settings(batfish_port="PRIVATE_BAD_PORT")
    assert "PRIVATE_BAD_PORT" not in str(failure.value)


def context():
    return AnalysisContext(
        network_id=uuid4(),
        snapshot_id=uuid4(),
        engine_network="n",
        engine_snapshot="s",
        engine_version="revision",
        sdk_version="2026.9.17.3748",
        schema_version="1",
    )


def test_contracts_are_json_serializable_and_jobs_are_deeply_immutable():
    source = {"headers": {"ports": [443]}}
    job = JobDTO(
        id=uuid4(),
        kind="analysis",
        resource_ids={"snapshot_id": uuid4()},
        requested_parameters=source,
        effective_parameters=source,
        created_by=uuid4(),
        status="queued",
        phase="queued",
        attempt=0,
        engine_state="idle",
        cancel_allowed=True,
        created_at=datetime.now(UTC),
    )
    source["headers"]["ports"].append(80)
    assert job.requested_parameters["headers"]["ports"] == (443,)
    with pytest.raises(TypeError):
        job.requested_parameters["headers"]["new"] = 1
    with pytest.raises(ValidationError):
        job.status = "running"
    assert json.loads(job.model_dump_json())["effective_parameters"]["headers"]["ports"] == [443]
    assert JobDTO.model_validate_json(job.model_dump_json()) == job
    actor = Actor(user_id=uuid4(), role="member", enabled=True)
    assert json.loads(actor.model_dump_json())["role"] == "member"
    result = ResultEnvelope(
        id=uuid4(),
        kind="table",
        schema_version="1",
        context=context(),
        effective_parameters={},
        summary={},
        warnings=(),
        coverage="unknown",
        truncated=False,
        created_at=datetime.now(UTC),
    )
    assert result.model_dump(mode="json")["context"]["engine_network"] == "n"


def test_contracts_reject_unknown_fields_invalid_json_and_naive_time():
    with pytest.raises(ValidationError):
        Actor(user_id=uuid4(), role="admin", enabled=True, unexpected=True)
    base = dict(
        id=uuid4(),
        kind="table",
        schema_version="1",
        context=context(),
        effective_parameters={},
        summary={},
        warnings=(),
        coverage="unknown",
        truncated=False,
        created_at=datetime.now(UTC),
    )
    for override in (
        {"summary": {"bad": object()}},
        {"summary": {"bad": float("nan")}},
        {"created_at": datetime(2026, 1, 1)},
        {"truncated": True},
    ):
        with pytest.raises(ValidationError):
            ResultEnvelope(**(base | override))


def test_empty_sdk_key_uses_default_and_rate_window_matches_operations(monkeypatch):
    monkeypatch.setenv("BATFISH_API_KEY", "")
    settings = Settings()
    assert settings.batfish_api_key is None
    assert settings.auth_failure_limit == 5
    assert settings.auth_failure_window_seconds == 60
