"""How numbers travel on the wire (D23).

A2A carries extension params and data parts as protobuf Struct values, which have no integer type:
4 arrives as 4.0, and 9007199254740993 as 9007199254740992. So every number is a decimal string.
"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

COUNT = r"^(0|[1-9][0-9]*)$"
AMOUNT = r"^(0|[1-9][0-9]*)(\.[0-9]+)?$"
TIMESTAMP = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"


class Wire(BaseModel):
    """Every protocol object: strict, like Zanni's files (D10, D22)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


Count = Annotated[str, Field(pattern=COUNT, description="A whole number, at least 0, as a decimal string, e.g. \"4\".")]
Seconds = Annotated[str, Field(pattern=COUNT, description="A duration in whole seconds, as a decimal string, e.g. \"30\".")]
Timestamp = Annotated[str, Field(pattern=TIMESTAMP, description="RFC 3339, in UTC, e.g. \"2026-10-24T09:30:00Z\".")]


class Money(Wire):
    """An amount of money. `amount` is a decimal string, so it is exact."""

    amount: Annotated[str, Field(pattern=AMOUNT, description="At least 0, e.g. \"20.10\".")]
    currency: Literal["USD"] = Field(description="ISO 4217. The first version uses USD only (D7).")


def _ordered(r: "Range") -> "Range":
    if int(r.min) > int(r.max):
        raise ValueError(f"min ({r.min}) is more than max ({r.max})")
    return r


class Range(Wire):
    """A range of whole numbers, such as seats. A single number is min = max."""

    min: Count
    max: Count

    @model_validator(mode="after")
    def _check_order(self) -> "Range":
        return _ordered(self)


def count(n: int) -> str:
    return str(n)


def money(amount: Decimal | str) -> Money:
    return Money(amount=str(Decimal(str(amount))), currency="USD")
