from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="", env_file=None, extra="forbid", hide_input_in_errors=True, frozen=True
    )

    # Optional while the skeleton has no database; missing dependencies cannot be ready.
    database_url: SecretStr | None = Field(default=None, repr=False, exclude=True)
    batfish_host: str = Field(default="localhost", min_length=1, repr=False, exclude=True)
    batfish_port: int = Field(default=9996, ge=1, le=65535, repr=False, exclude=True)
    batfish_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    batfish_tls: bool = False
    sdk_request_timeout: float = Field(default=120, gt=0, allow_inf_nan=False)
    sdk_concurrency: Literal[1] = 1
    readiness_max_age_seconds: float = Field(default=60, gt=0, allow_inf_nan=False)
