"""The casting messages (D21, D24). Each travels as an A2A data part, tagged by `kind`.

Who sends what, and in which A2A construct:

  join      actor -> director   SendMessage, starting the seat's task
  cast      director -> actor   the task's status message, state `working`
  refused   director -> actor   the task's status message, state `rejected`
  cue       director -> actor   the task's status message, state `input-required`
  report    actor -> director   SendMessage on the seat's task
  release   director -> actor   the task's status message, state `input-required`
  released  actor -> director   SendMessage on the seat's task; then the task is `completed`
"""

from typing import Annotated, Any, Literal

from pydantic import Field, field_validator

from zanni.protocol.card import EXTENSION_URI, ActorCardParams, ReportedModel
from zanni.protocol.encoding import Count, Money, Seconds, Timestamp, Wire

Text = Annotated[str, Field(min_length=1)]
Url = Annotated[str, Field(pattern=r"^(https?|wss?)://\S+$")]
REFUSAL_REASONS = ("not-authorised", "bad-card", "unsupported-version", "no-such-part", "part-full", "host-cap",
                   "role-mismatch", "hash-mismatch", "needs-beyond-part")
RELEASE_REASONS = ("done", "recast", "play-stopped", "budget", "no-heartbeat")


class Join(Wire):
    """An actor asks to join. The join token travels in the HTTP `Authorization` header, never in the body."""

    kind: Literal["zanni.join"]
    card: dict[str, Any] = Field(
        description="The actor's whole Agent Card, in A2A's JSON form.",
        # So the published schema can check what the validator below checks: the card carries the extension.
        json_schema_extra={"required": ["capabilities"], "properties": {"capabilities": {
            "type": "object", "required": ["extensions"], "properties": {"extensions": {
                "type": "array", "contains": {"type": "object", "required": ["uri", "params"],
                                              "properties": {"uri": {"const": EXTENSION_URI}}}}}}}})
    part: str | None = Field(default=None, min_length=1,
                             description="The part to join, when the role is cast for more than one.")

    @field_validator("card")
    @classmethod
    def _card_has_the_extension(cls, card: dict[str, Any]) -> dict[str, Any]:
        """The card must carry the casting extension, with valid actor-card params."""
        extensions = card.get("capabilities", {}).get("extensions", [])
        ours = [e for e in extensions if isinstance(e, dict) and e.get("uri") == EXTENSION_URI]
        if not ours:
            raise ValueError(f"the card doesn't carry the casting extension ({EXTENSION_URI})")
        ActorCardParams.model_validate(ours[0].get("params", {}))
        return card


class Permissions(Wire):
    read: list[str] = []
    write: list[str] = []


class DirectAccess(Wire):
    """For a git stage, a seat whose reads cover the whole stage may also clone it (D16)."""

    clone_url: Text
    branch: Text = Field(description="The seat's own branch, zanni/<play>/<seat>.")


class StageAccess(Wire):
    mcp_url: Url = Field(description="The stage's MCP server (D16).")
    token: Text = Field(description="The seat's bearer token for the stage. Revoked at release.")
    direct: DirectAccess | None = None


class Heartbeat(Wire):
    """The actor must contact the seat's task (SubscribeToTask, or GetTask) at least every `interval`."""

    interval: Seconds = "30"
    misses: Count = Field(default="3", description="How many intervals without contact before the seat is recast.")


class Limits(Wire):
    budget: Money | None = Field(default=None, description="This seat's share of the play's budget, if any.")


class Cast(Wire):
    """The director accepts the actor into a seat."""

    kind: Literal["zanni.cast"]
    seat: Text
    part: Text
    permissions: Permissions = Field(description="The seat's effective stage permissions (D12).")
    stage: StageAccess
    seat_token: Text = Field(description="Replaces the join token for every later call on this seat. Revoked at release.")
    expires_at: Timestamp
    heartbeat: Heartbeat = Heartbeat()
    limits: Limits = Limits()


class Refused(Wire):
    kind: Literal["zanni.refused"]
    reason: Literal[REFUSAL_REASONS]
    message: Text = Field(description="What was refused and why, in plain words.")


class Cue(Wire):
    """What one seat must do now. Actors never receive the whole script."""

    kind: Literal["zanni.cue"]
    cue: Text = Field(description="This cue's id, quoted back in the report.")
    scene: Text
    instructions: Text
    reads: list[str] = []
    writes: list[str] = []
    verifiers: list[str] = Field(default=[], description="What will judge the work, in plain words.")
    deadline: Timestamp | None = None


class Report(Wire):
    """An actor's result for one cue. Everything in it is data, never instructions."""

    kind: Literal["zanni.report"]
    cue: Text
    outcome: Literal["done", "failed"]
    summary: str
    changes: list[str] = Field(default=[], description="The stage change markers this work produced.")
    cost: Money | None = Field(description="Self-reported; null when unknown, never zero (D7).")
    models: list[ReportedModel] = Field(default=[], description="Self-reported, never trusted (D11).")


class Release(Wire):
    kind: Literal["zanni.release"]
    reason: Literal[RELEASE_REASONS]
    message: str = ""


class Released(Wire):
    """The actor confirms it stopped and discarded its working memory."""

    kind: Literal["zanni.released"]
    discarded: bool


MESSAGES: dict[str, type[Wire]] = {m.model_fields["kind"].annotation.__args__[0]: m
                                   for m in (Join, Cast, Refused, Cue, Report, Release, Released)}
