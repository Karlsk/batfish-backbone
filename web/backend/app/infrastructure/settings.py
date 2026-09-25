from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="", env_file=None, extra="forbid", hide_input_in_errors=True, frozen=True
    )

    # Live health remains available without DB; business services require it.
    database_url: SecretStr | None = Field(default=None, repr=False, exclude=True)
    batfish_host: str = Field(default="localhost", min_length=1, repr=False, exclude=True)
    batfish_port: int = Field(default=9996, ge=1, le=65535, repr=False, exclude=True)
    batfish_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    batfish_tls: bool = False
    sdk_request_timeout: float = Field(default=120, gt=0, allow_inf_nan=False)
    sdk_concurrency: Literal[1] = 1
    readiness_max_age_seconds: float = Field(default=60, gt=0, allow_inf_nan=False)
    auth_allowed_origins: tuple[str, ...] = ()
    auth_cookie_secure: bool = True
    auth_failure_limit: int = Field(default=5, ge=1, le=100)
    auth_failure_window_seconds: int = Field(default=900, ge=60, le=86400)

    @field_validator("auth_allowed_origins")
    @classmethod
    def validate_origins(cls, origins):
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
                or origin == "null"
            ):
                raise ValueError("Expected exact HTTP(S) origins without paths or credentials")
        return origins
