from pydantic import Field, JsonValue

from app.contracts.base import Contract


class ExpertQueryRequest(Contract):
    question_id: str = Field(min_length=1, max_length=128)
    parameters: dict[str, JsonValue]
