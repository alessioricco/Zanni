"""What the engine's A2A server asks of the director's casting side, and gets back. Plain data: no engine types.

The engine (src/zanni/engine/a2a_server.py) owns HTTP, A2A tasks and the MCP server; the director
(src/zanni/director/) owns every decision: who is cast, what each seat does next, and when a seat ends (D29).
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from zanni.actor.contract import Stage
from zanni.protocol.messages import Cast, Cue, Join, Refused, Release, Released, Report

TaskState = Literal["working", "input-required", "completed", "canceled", "rejected"]


@dataclass(frozen=True)
class Outgoing:
    """The seat's next task status: a cue or a release (input-required), or the end of the task."""

    state: TaskState
    message: Cue | Release | None = None


@dataclass(frozen=True)
class DirectorInfo:
    """What the director's Agent Card says about it (docs/spec/casting-extension.md, "The director's card")."""

    name: str
    description: str
    version: str
    play: str
    script: str


class Casting(Protocol):
    """The director's side of every seat. The engine calls these; it decides nothing itself."""

    async def join(self, token: str | None, task_id: str, join: Join | None, problem: str | None,
                   reached_at: str) -> Cast | Refused:
        """A join on a new task. When the message or its card isn't valid, `join` is None and `problem` says why,
        as `<reason>: <message>` with the reason `bad-card` or `unsupported-version`.

        `reached_at` is the base URL the actor reached the director by (from the request's Host), so the
        cast's stage address works from wherever the actor is.
        """

    async def next_for(self, task_id: str) -> Outgoing:
        """Wait for the seat's next cue or release."""

    async def report(self, task_id: str, report: Report) -> None: ...

    async def released(self, task_id: str, released: Released) -> None: ...

    def ending(self, task_id: str) -> Outgoing:
        """The final status of a task the director is ending itself, such as a seat with no heartbeat."""

    def authorise(self, token: str | None, task_id: str) -> str | None:
        """None if `token` is this task's seat token and still valid; otherwise what is wrong, in plain words."""

    def contact(self, task_id: str, streaming: bool | None = None) -> None:
        """The actor contacted its task (D21). `streaming` is True when a stream opens, False when it closes."""

    def stage_for(self, stage_token: str) -> Stage | None:
        """The stage, with its seat's permissions, for a valid stage token; None otherwise (D31)."""
