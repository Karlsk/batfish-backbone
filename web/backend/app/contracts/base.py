import math
from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


def freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite numbers are not valid contract values")
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    return value


def thaw(value):
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw(item) for item in value]
    return value


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, hide_input_in_errors=True
    )

    @field_validator("*", mode="after")
    @classmethod
    def freeze_fields(cls, value):
        # frozen=True alone does not protect dictionaries nested in a JobDTO.
        return freeze(value)

    @field_serializer("*", mode="wrap")
    def serialize_frozen_fields(self, value, handler):
        if isinstance(value, Mapping):
            value = thaw(value)
        elif isinstance(value, tuple):
            value = tuple(thaw(item) for item in value)
        return handler(value)
