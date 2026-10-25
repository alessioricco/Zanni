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
    """`/` covers the whole stage; a rule ending in `/` covers a folder and everything under it;
    any other rule covers exactly one path."""
    if rule == "/":
        return True
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
    max_output: int | None = Field(default=None, ge=1)  # the most tokens in one response; none: the provider's (D61)

    @model_validator(mode="after")
    def _endpoint(self) -> "ModelEntry":
        if self.provider == "openai-compatible" and not self.base_url:
            raise ValueError("an openai-compatible model needs a `base_url`; add the server's URL, e.g. http://gpu-box:8000/v1")
        return self


DIRECTOR_ROLE = "zanni:director"  # Zanni's built-in director role, shipped in the package (D34)
VERIFIER_ROLE = "zanni:verifier"  # Zanni's built-in verifier seat: runs verifiers' commands, no model (D45)
BUILT_IN_ROLES = (DIRECTOR_ROLE, VERIFIER_ROLE)


def _role_ref(value: object) -> object:
    """A package reference, or one of Zanni's built-in roles."""
    if isinstance(value, str) and value.startswith("zanni:"):
        if value not in BUILT_IN_ROLES:
            raise ValueError(f'"{value}" is not one of Zanni\'s built-in roles; use {" or ".join(BUILT_IN_ROLES)}')
        return value
    return _package_ref(value)


class ToolPrice(Strict):
    per_call: Decimal = Field(ge=0)  # USD the play is charged for each call to the tool (D53)


class ToolBinding(Strict):
    """A server the actor brings for one of its role's tools, in mcp.json's shape, with what it charges (D53)."""

    command: str | None = Field(default=None, min_length=1)
    args: list[str] = []
    env: dict[str, str] = {}
    url: str | None = Field(default=None, min_length=1)
    headers: dict[str, str] = {}
    price: ToolPrice | None = None  # none: the tool's cost is unknown, never zero (D7)

    @model_validator(mode="after")
    def _command_or_url(self) -> "ToolBinding":
        if bool(self.command) == bool(self.url):
            raise ValueError("a tool needs exactly one of `command` (a server the actor starts) or `url` "
                             "(a server it reaches); give one")
        if self.command and self.command.startswith("zanni:"):
            raise ValueError(f'"{self.command}" is a server Zanni ships; a role names it in its mcp.json, and a '
                             "binding brings a server of the actor's own")
        if self.url and (self.args or self.env):
            raise ValueError("`args` and `env` are for a server the actor starts; a `url` server takes `headers`")
        if self.command and self.headers:
            raise ValueError("`headers` are for a server reached by `url`; a `command` server takes `args` and `env`")
        return self


class Workspace(Strict):
    commands: list[Annotated[str, Field(min_length=1)]] = []  # what `run` may start on this machine; none: nothing (D52)


class VerifierSeats(Strict):
    """Where a director lets its play's verifiers run, besides its own machine (D45)."""

    local: list[Annotated[str, Field(min_length=1)]] = []  # verifier configurations the director starts
    remote: list[Annotated[str, Field(min_length=1)]] = []  # names of verifier seats that join from elsewhere


class ActorConfiguration(Strict):
    """One actor instance: its role, its play, its models and its credentials. Never the role's capabilities (D14).

    With `role: zanni:director` it is a director configuration: the director's own models and credentials, and the
    actor configurations it starts for local seats (D34, D36). With `role: zanni:verifier` it is a verifier seat's,
    which runs no model (D45).
    """

    SECRET_SECTIONS: ClassVar[tuple[str, ...]] = ("credentials",)
    REFERENCE_SECTIONS: ClassVar[tuple[tuple[str, ...], ...]] = (("tools", "*", "env"), ("tools", "*", "headers"))

    name: str | None = Field(default=None, min_length=1)
    role: Annotated[str, BeforeValidator(_role_ref)]
    play: str = Field(min_length=1)
    models: list[ModelEntry] = Field(default_factory=list, validate_default=True)
    credentials: dict[EnvName, str] = {}  # this instance's own; protected by D15's safeguards
    state_dir: str | None = None  # default: ~/.zanni/actors/<name>
    seats: dict[str, list[Annotated[str, Field(min_length=1)]]] = {}  # director only: part -> actor configurations
    verifier_seats: VerifierSeats = VerifierSeats()  # director only: verifier seats it trusts (D45)
    tools: dict[str, ToolBinding] = {}  # servers this actor brings for its role's tools (D53)
    workspace: Workspace = Workspace()  # what a workspace may run on this machine (D52)

    @field_validator("models")
    @classmethod
    def _models_unless_verifier(cls, models: list, info) -> list:
        if info.data.get("role") == VERIFIER_ROLE:
            if models:
                raise ValueError("a verifier seat runs no model; remove `models`")
        elif not models:
            raise ValueError("is required: list at least one model this actor runs, e.g. "
                             "- { provider: anthropic, model: claude-haiku-5-5 }")
        return models

    @model_validator(mode="after")
    def _credentials_exist(self) -> "ActorConfiguration":
        for i, entry in enumerate(self.models):
            if entry.credential and entry.credential not in self.credentials:
                raise ValueError(f"models[{i}] uses the credential {entry.credential}, which isn't in `credentials`; "
                                 f"add {entry.credential} to `credentials`, or remove `credential` to use the environment")
        return self

    @field_validator("seats")
    @classmethod
    def _seats_for_a_director(cls, seats: dict, info) -> dict:
        if seats and info.data.get("role") != DIRECTOR_ROLE:
            raise ValueError(f"`seats` lists local seats for a director; only a configuration with "
                             f"role: {DIRECTOR_ROLE} may have it. Remove it, or make this the director's configuration")
        return seats

    @field_validator("verifier_seats")
    @classmethod
    def _verifier_seats_for_a_director(cls, seats: "VerifierSeats", info) -> "VerifierSeats":
        if (seats.local or seats.remote) and info.data.get("role") != DIRECTOR_ROLE:
            raise ValueError(f"`verifier_seats` lists the verifier seats a director trusts; only a configuration with "
                             f"role: {DIRECTOR_ROLE} may have it")
        return seats

    @field_validator("tools", "workspace")
    @classmethod
    def _not_for_built_in_roles(cls, value, info):
        role = info.data.get("role")
        if role in BUILT_IN_ROLES and value not in ({}, Workspace()):
            raise ValueError(f"the built-in role {role} has no tools to bind and runs no workspace; "
                             f"remove `{info.field_name}`")
        return value

    @property
    def is_director(self) -> bool:
        return self.role == DIRECTOR_ROLE

    @property
    def is_verifier(self) -> bool:
        return self.role == VERIFIER_ROLE

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


def _duration(value: object) -> object:
    """Whole seconds (`90`), or a number with s, m or h (`90s`, `30m`, `2h`)."""
    if isinstance(value, bool):
        raise ValueError("should be a duration such as 3600, 30m or 2h")
    if isinstance(value, str):
        m = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", value)
        if not m:
            raise ValueError(f'"{value}" is not a duration; write whole seconds, or a number with s, m or h, e.g. 30m')
        return int(m[1]) * {"": 1, "s": 1, "m": 60, "h": 3600}[m[2]]
    return value


Duration = Annotated[int, BeforeValidator(_duration), Field(ge=1)]


class HouseRules(Strict):
    budget: Decimal | None = Field(default=None, ge=0)  # in USD, for the whole play
    gates: list[str] = []  # moments that need human approval; must be among the script's gates
    max_seats_per_host: int | None = Field(default=None, ge=1)  # actors on one machine share its GPU
    gate_timeout: Duration | None = None  # seconds a gate or a pause may wait; none: it waits (D38)
    max_director_turns: int = Field(default=30, ge=1)  # the director's model turns in one round (D33)
    requests_per_turn: int = Field(default=25, ge=1)  # model requests in one director turn (D49)
    cast_timeout: Duration = 600  # seconds a part may wait below its minimum seats for an actor to join (D50)
    max_rounds: int | None = Field(default=None, ge=1)  # at most the script's stop.max_rounds; none: the script's (D58)


GIT_URL = re.compile(r"^(git@[^:\s]+:\S+|(ssh|git|https?)://\S+\.git/?|\S+\.git/?)$")


def _stage(value: object) -> object:
    """A plain string is shorthand: a git URL or .git path means `git`, anything else is a local folder."""
    if isinstance(value, str):
        return {"backend": "git", "url": value} if GIT_URL.match(value.strip()) else {"backend": "folder", "path": value}
    return value


class Stage(Strict):
    """The play's workspace and the backend that stores it; the director enforces each seat's permissions (D43)."""

    backend: Literal["git", "folder", "mcp"]
    url: str | None = Field(default=None, min_length=1)  # git: the repository; mcp: the server's endpoint
    branch: str = Field(default="main", min_length=1)  # git: the branch each run starts from
    push: Literal["approved", "always"] = "approved"  # git: when the director pushes the run's branch (D46)
    path: str | None = Field(default=None, min_length=1)  # folder: a folder on the director's machine

    @model_validator(mode="after")
    def _fields_match_backend(self) -> "Stage":
        git_only = [f for f in ("branch", "push") if f in self.model_fields_set]
        if self.backend == "git":
            if not self.url:
                raise ValueError("a git stage needs a `url`; add the repository, e.g. url: git@github.com:you/app.git")
            if self.path:
                raise ValueError("`path` is for folder stages; a git stage takes `url`, `branch` and `push`")
        elif self.backend == "mcp":
            if not self.url or not re.match(r"^https?://\S+$", self.url):
                raise ValueError("an mcp stage needs a `url`, the server's http(s) endpoint, e.g. "
                                 "url: http://docs.internal:8800/mcp")
            if self.path or git_only:
                raise ValueError("an mcp stage takes only `url`; `path` is for folder stages, `branch` and `push` "
                                 "for git stages")
        else:
            if not self.path:
                raise ValueError("a folder stage needs a `path`; add the folder, e.g. path: ./stage")
            if self.url or git_only:
                raise ValueError("`url`, `branch` and `push` are for git stages; a folder stage takes `path`")
        return self

    def __str__(self) -> str:
        if self.backend == "git":
            return f"git {self.url} (branch {self.branch}; pushes {self.push})"
        return f"mcp server {self.url}" if self.backend == "mcp" else f"folder {self.path}"


StageSpec = Annotated[Stage, BeforeValidator(_stage)]


def _director(value: object) -> object:
    if isinstance(value, str) and not re.match(r"^https?://\S+$", value):
        raise ValueError(f'"{value}" is not a director address; write an http(s) URL such as '
                         'https://director.example.com (D30)')
    return value


class PlayVerifier(Strict):
    """A play's own command for one of its script's verifiers, and where it runs (D35, D45)."""

    command: list[str] | None = Field(default=None, min_length=1)  # default: the script's
    timeout: int | None = Field(default=None, ge=1)  # seconds; default: the script's
    runs_on: str | None = Field(default=None, min_length=1)  # a verifier seat's name; default: the director


class PlayFile(Strict):
    """One production of a script: the director, the cast for the script's parts, the stage and the house rules."""

    name: str = Field(min_length=1)
    script: PackageRef
    director: Annotated[str, BeforeValidator(_director)] | None = None  # None: this machine runs the director
    stage: StageSpec
    cast: dict[str, CastSeat] = Field(min_length=1)  # part name -> role
    house_rules: HouseRules = HouseRules()
    verifiers: dict[str, PlayVerifier] = {}  # name -> command, overriding the script's (D35)


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
    done_when: list[Name] = []  # verifiers that must pass, after the stage's last change, for "done" (D35)


VERIFIER_TIMEOUT = 300  # seconds


def _package_path(value: object) -> object:
    """A path inside a package: relative, with `/`, no `..` and no empty segment."""
    if isinstance(value, str) and (value.startswith("/") or "\\" in value
                                   or any(seg in ("", ".", "..") for seg in value.split("/"))):
        raise ValueError(f'"{value}" is not a path inside the script\'s package; write it relative to the script\'s '
                         "folder, with /, e.g. checks/criteria.py")
    return value


class ScriptVerifier(Strict):
    """A check the director runs on a snapshot of the stage, by name: it passes when its command exits 0 (D35, D45)."""

    description: str = Field(min_length=1)  # what it checks, in plain words; the prose refers to it by name
    command: list[str] | None = Field(default=None, min_length=1)  # a default; a play may give its own
    timeout: int = Field(default=VERIFIER_TIMEOUT, ge=1)  # seconds
    files: list[Annotated[str, BeforeValidator(_package_path)]] = []  # check files, found as ${ZANNI_SCRIPT} (D55)


class Gate(Strict):
    """A moment that needs a person's approval: once per play, or every round; optionally before a part's cues (D48)."""

    name: Name
    every: Literal["play", "round"] = "play"
    before: list[Name] = []  # parts whose cues wait for this gate's approval
    before_writes: list[Annotated[str, Field(min_length=1)]] = []  # stage paths no cue may write until approved (D62)

    def holds(self) -> str:
        """What the gate holds back, in words: the parts it comes before, and the paths no cue writes until then."""
        bits = [f"before {', '.join(self.before)}"] if self.before else []
        if self.before_writes:
            bits.append(f"before any cue writes {', '.join(self.before_writes)}")
        return "; ".join(bits)


def _gate(value: object) -> object:
    return {"name": value} if isinstance(value, str) else value  # `- release` is shorthand for `{ name: release }`


class Script(Strict):
    """The reusable work: mission, parts, the workspace it expects, gates, verifiers and stop rules (D13, D17)."""

    name: Name
    version: Annotated[str, BeforeValidator(_version)]
    mission: str = Field(min_length=1)
    parts: dict[Name, Part] = Field(min_length=1)
    stage: ScriptStage = ScriptStage()
    gates: list[Annotated[Gate, BeforeValidator(_gate)]] = []
    verifiers: dict[Name, ScriptVerifier] = {}
    stop: StopRules = StopRules()

    @property
    def gate_names(self) -> list[str]:
        return [g.name for g in self.gates]

    def gate(self, name: str) -> Gate | None:
        return next((g for g in self.gates if g.name == name), None)


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

WORKSPACE_SERVER = "zanni:workspace"  # the only server Zanni ships for roles: a local copy of the stage (D52)
BUILT_IN_SERVERS = (WORKSPACE_SERVER,)


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
        if self.command and self.command.startswith("zanni:"):
            if self.command not in BUILT_IN_SERVERS:
                raise ValueError(f'"{self.command}" is not a server Zanni ships; use {" or ".join(BUILT_IN_SERVERS)}')
            if self.args or self.env or self.cwd:
                raise ValueError(f"{self.command} is built in, and takes no `args`, `env` or `cwd`; remove them")
        return self


class McpConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mcpServers: dict[str, McpServer]


# Rehearsal: one actor, run on cues against a local stage, with a director that plays only its cues (D26, D29)

class RehearsalCue(Strict):
    """One cue, as the director would give it (the `zanni.cue` message, without the ids)."""

    scene: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    reads: list[str] = []
    writes: list[str] = []
    verifiers: list[str] = []  # what will judge the work, in plain words, for the actor


class VerifyCommand(Strict):
    """A check run in the stage copy after the cues; it passes when the command exits 0."""

    name: Name
    command: list[str] = Field(min_length=1)


class Rehearsal(Strict):
    """Runs a role without a director: an actor configuration's `play` points here (D26)."""

    rehearsal: Name
    description: str | None = None
    stage: str = Field(min_length=1)  # a folder, relative to this file, copied fresh for every run
    cues: list[RehearsalCue] = Field(min_length=1)
    verify: list[VerifyCommand] = []
