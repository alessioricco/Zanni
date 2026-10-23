"""The kinds of Zanni file: actor configuration, play file and role manifest. Field names follow the vision doc."""

import re
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, field_validator, model_validator

REMOTE_REF = re.compile(r"^(?P<source>[a-z0-9-]+(\.[a-z0-9-]+)+/[^@\s]+)@(?P<version>[^@\s/]+)$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _package_ref(value: object) -> object:
    """A role or script reference: host/owner/name@version, or a local folder."""
    if not isinstance(value, str):
        return value
    if REMOTE_REF.match(value):
        return value
    first = value.split("/", 1)[0]
    if "@" not in value and "." in first and first not in (".", ".."):
        raise ValueError(f'"{value}" has no version; write it as {value}@1.0.0, with the version you want')
    if "@" in value:
        raise ValueError(f'"{value}" is not a package reference; write host/owner/name@version, '
                         "e.g. github.com/someone/tester@1.4.0")
    return value  # a local folder, e.g. roles/tester or ./roles/tester


PackageRef = Annotated[str, BeforeValidator(_package_ref)]


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


def covers(rule: str, path: str) -> bool:
    """A rule ending in `/` covers a folder and everything under it; any other rule covers exactly one path."""
    return path.startswith(rule) if rule.endswith("/") else path == rule


# Actor configuration

ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ENV_REF = re.compile(r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(:-[^}]*)?\}$")
FALLBACK_REASONS = ("error", "timeout", "rate-limit", "context", "refusal")


def _env_name(value: object) -> object:
    if isinstance(value, str) and not ENV_NAME.match(value):
        raise ValueError(f'"{value}" is not a credential name; use letters, digits and underscores, e.g. ANTHROPIC_API_KEY')
    return value


EnvName = Annotated[str, BeforeValidator(_env_name)]


class Price(Strict):
    input: Decimal = Field(ge=0)  # USD per million input tokens
    output: Decimal = Field(ge=0)  # USD per million output tokens


class ModelEntry(Strict):
    """One model the actor may run. The list is tried in order (D11)."""

    provider: Literal["anthropic", "openai", "google", "ollama", "openai-compatible"]
    model: str = Field(min_length=1)
    base_url: str | None = Field(default=None, min_length=1)  # a URL, or ${VAR}
    credential: EnvName | None = None  # a name in `credentials`; default: the provider's usual variable
    tool_format: Literal["native", "text"] = "native"  # text: the opt-in format for models without tool calling (D5)
    price: Price | None = None  # for models published prices don't cover, such as local ones (D7)
    fall_back_on: list[Literal["error", "timeout", "rate-limit", "context", "refusal"]] = \
        ["error", "timeout", "rate-limit", "context"]

    @model_validator(mode="after")
    def _endpoint(self) -> "ModelEntry":
        if self.provider == "openai-compatible" and not self.base_url:
            raise ValueError("an openai-compatible model needs a `base_url`; add the server's URL, e.g. http://gpu-box:8000/v1")
        return self


class ActorConfiguration(Strict):
    """One actor instance: its role, its play, its models and its credentials. Never the role's capabilities (D14)."""

    SECRET_SECTIONS: ClassVar[tuple[str, ...]] = ("credentials",)

    name: str | None = Field(default=None, min_length=1)
    role: PackageRef
    play: str = Field(min_length=1)
    models: list[ModelEntry] = Field(min_length=1)
    credentials: dict[EnvName, str] = {}  # this instance's own; protected by D15's safeguards
    state_dir: str | None = None  # default: ~/.zanni/actors/<name>
    port: int = Field(default=0, ge=0, le=65535)  # 0: any free port

    @model_validator(mode="after")
    def _credentials_exist(self) -> "ActorConfiguration":
        for i, entry in enumerate(self.models):
            if entry.credential and entry.credential not in self.credentials:
                raise ValueError(f"models[{i}] uses the credential {entry.credential}, which isn't in `credentials`; "
                                 f"add {entry.credential} to `credentials`, or remove `credential` to use the environment")
        return self

    def stored_credentials(self) -> list[str]:
        """Credentials whose values are in this file, not references to the environment."""
        return [k for k, v in self.credentials.items() if not ENV_REF.match(v)]


# Play file

class CastEntry(Strict):
    role: PackageRef
    seats: SeatRange | None = None  # None: the script part's seats, or 1 when the script isn't known
    host: str | None = None  # "local": the director starts these seats itself


def _cast_entry(value: object) -> object:
    return {"role": value} if isinstance(value, str) else value  # `tester: github.com/x/tester@1.0.0` is shorthand


CastSeat = Annotated[CastEntry, BeforeValidator(_cast_entry)]


class HouseRules(Strict):
    budget: Decimal | None = Field(default=None, ge=0)  # in USD, for the whole play
    gates: list[str] = []  # moments that need human approval; must be among the script's gates
    max_seats_per_host: int | None = Field(default=None, ge=1)  # actors on one machine share its GPU


GIT_URL = re.compile(r"^(git@[^:\s]+:\S+|(ssh|git|https?)://\S+\.git/?|\S+\.git/?)$")


def _stage(value: object) -> object:
    """A plain string is shorthand: a git URL or .git path means `git`, anything else is a local folder."""
    if isinstance(value, str):
        return {"backend": "git", "url": value} if GIT_URL.match(value.strip()) else {"backend": "folder", "path": value}
    return value


class Stage(Strict):
    """The play's workspace. The backend enforces each seat's permissions (D12)."""

    backend: Literal["git", "folder"]
    url: str | None = Field(default=None, min_length=1)  # git: the repository
    branch: str = Field(default="main", min_length=1)  # git: the branch seats start from and merge into
    path: str | None = Field(default=None, min_length=1)  # folder: a folder on the director's machine

    @model_validator(mode="after")
    def _fields_match_backend(self) -> "Stage":
        if self.backend == "git":
            if not self.url:
                raise ValueError("a git stage needs a `url`; add the repository, e.g. url: git@github.com:you/app.git")
            if self.path:
                raise ValueError("`path` is for folder stages; a git stage takes `url` and `branch`")
        else:
            if not self.path:
                raise ValueError("a folder stage needs a `path`; add the folder, e.g. path: ./stage")
            if self.url or "branch" in self.model_fields_set:
                raise ValueError("`url` and `branch` are for git stages; a folder stage takes `path`")
        return self

    def __str__(self) -> str:
        return f"git {self.url} (branch {self.branch})" if self.backend == "git" else f"folder {self.path}"


StageSpec = Annotated[Stage, BeforeValidator(_stage)]


def _director(value: object) -> object:
    if isinstance(value, str) and not re.match(r"^(wss?|https?)://\S+$", value):
        raise ValueError(f'"{value}" is not a director address; write a URL such as wss://director.example.com')
    return value


class PlayFile(Strict):
    """One production of a script: the director, the cast for the script's parts, the stage and the house rules."""

    name: str = Field(min_length=1)
    script: PackageRef
    director: Annotated[str, BeforeValidator(_director)] | None = None  # None: this machine runs the director
    stage: StageSpec
    cast: dict[str, CastSeat] = Field(min_length=1)  # part name -> role
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

    @field_validator("outputs")
    @classmethod
    def _outputs_inside_writes(cls, outputs: dict[str, str], info) -> dict[str, str]:
        needs = info.data.get("needs")
        writes = needs.stage_write if needs else []
        for path in outputs:
            if not any(covers(rule, path) for rule in writes):
                raise ValueError(f'"{path}" is not inside needs.stage_write; '
                                 f"add its folder to needs.stage_write, or write it to one of: {', '.join(writes) or 'nothing yet'}")
        return outputs


# Script (SCRIPT.md frontmatter; the prose after it is for the director)

NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _name(value: object) -> object:
    if isinstance(value, str) and not NAME.match(value):
        raise ValueError(f'"{value}" is not a valid name; use lowercase letters, digits and dashes, e.g. product-owner')
    return value


Name = Annotated[str, BeforeValidator(_name)]


class Part(Strict):
    """A part the script needs. Its `reads` and `writes` are ceilings on what the seat may touch (D12)."""

    description: str | None = None
    suggested: PackageRef | None = None  # a role the play may cast, or replace
    seats: SeatRange = Seats(min=1, max=1)
    reads: list[str] | None = None
    writes: list[str] | None = None
    optional: bool = False


class ScriptStage(Strict):
    expects: list[str] = []  # paths the stage must hold before the play starts


class StopRules(Strict):
    max_rounds: int | None = Field(default=None, ge=1)
    budget_per_round: Decimal | None = Field(default=None, ge=0)  # USD


class Script(Strict):
    """The reusable work: mission, parts, the workspace it expects, gates and stop rules (D13, D17)."""

    name: Name
    version: Annotated[str, BeforeValidator(_version)]
    mission: str = Field(min_length=1)
    parts: dict[Name, Part] = Field(min_length=1)
    stage: ScriptStage = ScriptStage()
    gates: list[Name] = []
    stop: StopRules = StopRules()


# Lockfile (play.lock): what each package reference resolved to

COMMIT = re.compile(r"^[0-9a-f]{40}$")
HASH = re.compile(r"^sha256:[0-9a-f]{64}$")


def _pattern(regex: re.Pattern, what: str, example: str):
    def check(value: object) -> object:
        if isinstance(value, str) and not regex.match(value):
            raise ValueError(f'"{value}" is not {what}; write it as {example}')
        return value
    return BeforeValidator(check)


class Pin(Strict):
    commit: Annotated[str, _pattern(COMMIT, "a full commit hash", "40 lowercase hex characters")] | None = None
    hash: Annotated[str, _pattern(HASH, "a content hash", "sha256: followed by 64 lowercase hex characters")]


class Lockfile(Strict):
    """Pins the play's script and roles (D18). A remote reference needs a commit; a local folder only a hash."""

    lock_version: Literal[1]
    script: dict[PackageRef, Pin] = Field(min_length=1, max_length=1)
    roles: dict[PackageRef, Pin] = {}

    @field_validator("script", "roles")
    @classmethod
    def _remote_refs_have_commits(cls, pins: dict[str, Pin]) -> dict[str, Pin]:
        for ref, pin in pins.items():
            if REMOTE_REF.match(ref) and pin.commit is None:
                raise ValueError(f"{ref} is a remote package, so it needs a `commit`; add the commit it resolved to")
        return pins


# SKILL.md frontmatter, per the Agent Skills spec (agentskills.io/specification). A standard, not Zanni's
# own format: its rules are enforced, and fields it doesn't define are left alone for other tools.

SKILL_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _skill_name(value: object) -> object:
    if isinstance(value, str) and not (len(value) <= 64 and SKILL_NAME.match(value)):
        raise ValueError(f'"{value}" is not a valid skill name; use 1-64 lowercase letters, digits and single hyphens, '
                         "not starting or ending with a hyphen")
    return value


class SkillFrontmatter(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: Annotated[str, BeforeValidator(_skill_name)]
    description: str = Field(min_length=1, max_length=1024)
    license: str | None = None
    compatibility: str | None = Field(default=None, min_length=1, max_length=500)
    metadata: dict[str, str] = {}
    allowed_tools: str | None = Field(default=None, alias="allowed-tools")


# mcp.json, the standard `mcpServers` format shared with Claude Desktop, Claude Code and Cursor.
# Server entries may carry keys other clients use (type, disabled, ...); those are left alone.

class McpServer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    command: str | None = Field(default=None, min_length=1)
    args: list[str] = []
    env: dict[str, str] = {}
    cwd: str | None = None
    url: str | None = Field(default=None, min_length=1)
    headers: dict[str, str] = {}

    @model_validator(mode="after")
    def _command_or_url(self) -> "McpServer":
        if bool(self.command) == bool(self.url):
            raise ValueError("a server needs exactly one of `command` (a local process) or `url` (a remote server)")
        return self


class McpConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mcpServers: dict[str, McpServer]
