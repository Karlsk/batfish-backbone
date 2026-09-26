"""Shared, validated node and VRF selectors for analysis requests."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.contracts.base import Contract

Name = Annotated[
    str, StringConstraints(min_length=1, max_length=255, pattern=r"^[^\x00-\x1f\x7f]+$")
]
Expression = Annotated[
    str, StringConstraints(min_length=1, max_length=4096, pattern=r"^[^\x00-\x1f\x7f]+$")
]


class LiteralSelector(Contract):
    mode: Literal["literal"]
    values: tuple[Name, ...] = Field(min_length=1, max_length=100)


class ExpressionSelector(Contract):
    mode: Literal["expression"]
    expression: Expression


Selector = Annotated[LiteralSelector | ExpressionSelector, Field(discriminator="mode")]
