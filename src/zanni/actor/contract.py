"""What Zanni hands the engine for one cue, and what it gets back. Plain data: no engine types.

The engine (src/zanni/engine/) is the only part that knows Pydantic AI, MCP or A2A (golden rule 4, D1).
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from zanni.files.schemas import ModelEntry


class StageError(Exception):
    """A refused stage operation; `code` is one of the stage spec's errors (docs/spec/stage.md)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Stage(Protocol):
    """The stage operations every backend offers (docs/spec/stage.md), for one seat."""

    def read(self, path: str) -> str: ...
    def write(self, path: str, content: str) -> str: ...
    def list(self, path: str = "") -> list[str]: ...
    def delete(self, path: str) -> str: ...
    def changes(self, since: str | None = None) -> tuple[list[tuple[str, str]], str]: ...


@dataclass(frozen=True)
class McpServerSpec:
    """One server from the role's mcp.json, with every ${NAME} already resolved (D20)."""

    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedModel:
    """A model entry from the actor configuration, with its credential and base URL resolved (D20)."""

    entry: ModelEntry
    api_key: str | None = None
    base_url: str | None = None

    def label(self) -> str:
        return f"{self.entry.provider} {self.entry.model}"


@dataclass(frozen=True)
class CueTask:
    instructions: str  # the role's AGENTS.md, then its skills' names and descriptions (D4)
    skills: dict[str, str]  # skill name -> body, served by the `load_skill` tool
    prompt: str  # the cue, as the actor receives it
    stage: Stage
    models: list[ResolvedModel]  # in order (D11); the next is tried on the entry's fall_back_on reasons (D20)
    mcp_servers: list[McpServerSpec] = field(default_factory=list)
    needs_tools: bool = False  # the role's model.needs.tools


@dataclass(frozen=True)
class Fallback:
    model: str
    reason: str  # one of FALLBACK_REASONS
    detail: str


@dataclass(frozen=True)
class CueResult:
    output: str
    model: str  # the model that produced the output, as "provider model"
    provider: str
    model_name: str
    tool_calls: list[str]
    input_tokens: int
    output_tokens: int
    requests: int
    cost: Decimal | None  # None when unknown, never zero (D7)
    cost_source: str  # "genai-prices", "configuration" or "unknown"
    fallbacks: list[Fallback] = field(default_factory=list)


class AllModelsFailed(Exception):
    """Every model in the list failed, or one failed for a reason its entry doesn't fall back on."""

    def __init__(self, fallbacks: list[Fallback]):
        self.fallbacks = fallbacks
        super().__init__("; ".join(f"{f.model}: {f.reason} ({f.detail})" for f in fallbacks))
