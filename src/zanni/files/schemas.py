"""The three kinds of Zanni file: actor file, play file and role manifest. Field names follow the vision doc."""

import re
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer

REMOTE_ROLE = re.compile(r"^(?P<source>[a-z0-9-]+(\.[a-z0-9-]+)+/[^@\s]+)@(?P<version>[^@\s/]+)$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _role_ref(value: object) -> object:
    if not isinstance(value, str):
        return value
    if REMOTE_ROLE.match(value):
        return value
    first = value.split("/", 1)[0]
    if "@" not in value and "." in first and first not in (".", ".."):
        raise ValueError(f'"{value}" has no version; write it as {value}@1.0.0, with the version you want')
    if "@" in value:
        raise ValueError(f'"{value}" is not a role reference; write host/owner/name@version, '
                         "e.g. github.com/someone/tester@1.4.0")
    return value  # a local folder, e.g. roles/tester or ./roles/tester


RoleRef = Annotated[str, BeforeValidator(_role_ref)]


class Seats(Strict):
    min: int
    max: int

    def __str__(self) -> str:
        return str(self.min) if self.min == self.max else f"{self.min}-{self.max}"


def _seats(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("should be a number of seats such as 2, or a range such as 1-4")
    if isinstance(value, int):
        value = str(value)
    if isinstance(value, str):
        m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", value)
        if not m:
            raise ValueError(f'"{value}" is not a number of seats; write a number such as 2, or a range such as 1-4')
        lo, hi = int(m[1]), int(m[2] or m[1])
        if lo < 1:
            raise ValueError("needs at least 1 seat; use 1 or more")
        if lo > hi:
            raise ValueError(f"the range {lo}-{hi} goes down; write the smaller number first: {hi}-{lo}")
        return {"min": lo, "max": hi}
    return value


SeatRange = Annotated[Seats, BeforeValidator(_seats), PlainSerializer(str)]


# Actor file

class ActorFile(Strict):
    """Which role to play, and in which play. Everything else comes from the director."""

    role: RoleRef
    play: str = Field(min_length=1)


# Play file

class CastEntry(Strict):
    role: RoleRef
    seats: SeatRange = Seats(min=1, max=1)
    host: str | None = None  # "local": the director starts these seats itself


def _cast_entry(value: object) -> object:
    return {"role": value} if isinstance(value, str) else value  # `tester: github.com/x/tester@1.0.0` is shorthand


CastSeat = Annotated[CastEntry, BeforeValidator(_cast_entry)]


class HouseRules(Strict):
    budget: Decimal | None = Field(default=None, ge=0)  # in USD, for the whole play
    gates: list[str] = []  # moments that need human approval, e.g. plan, release


def _director(value: object) -> object:
    if isinstance(value, str) and not re.match(r"^(wss?|https?)://\S+$", value):
        raise ValueError(f'"{value}" is not a director address; write a URL such as wss://director.example.com')
    return value


class PlayFile(Strict):
    """A play: the director, the stage, the cast, the script and the house rules."""

    name: str = Field(min_length=1)
    director: Annotated[str, BeforeValidator(_director)] | None = None  # None: this machine runs the director
    stage: str = Field(min_length=1)
    script: str | None = None
    cast: dict[str, CastSeat] = Field(min_length=1)
    house_rules: HouseRules = HouseRules()


# Role manifest (role.yaml)

def _context(value: object) -> object:
    if isinstance(value, str) and not re.fullmatch(r"\d+[kKmM]?", value):
        raise ValueError(f'"{value}" is not a context size; write tokens as a number, or with k or m, e.g. 32k')
    return value


class ModelNeeds(Strict):
    tools: bool = False
    context: Annotated[int | str, BeforeValidator(_context)] | None = None
    tier: str | None = None


class RoleModel(Strict):
    needs: ModelNeeds = ModelNeeds()
    suggested: str | None = None


class RoleNeeds(Strict):
    stage_read: list[str] = []
    stage_write: list[str] = []
    tools: list[str] = []


def _version(value: object) -> object:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        raise ValueError(f'{value} was read as a number; write the version in quotes as major.minor.patch, e.g. "1.4.0"')
    if isinstance(value, str) and not SEMVER.match(value):
        raise ValueError(f'"{value}" is not a version; write major.minor.patch, e.g. 1.4.0')
    return value


class RoleManifest(Strict):
    """Zanni's fields for a role; character and instructions live in AGENTS.md beside it."""

    name: str = Field(min_length=1)
    version: Annotated[str, BeforeValidator(_version)]
    mission: str = Field(min_length=1)
    model: RoleModel = RoleModel()
    needs: RoleNeeds = RoleNeeds()
    never: list[str] = []
    outputs: dict[str, str] = {}
