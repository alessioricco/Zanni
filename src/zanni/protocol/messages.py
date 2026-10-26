"""The casting messages (D21, D24). Each travels as an A2A data part, tagged by `kind`.

Who sends what, and in which A2A construct:

  join      actor -> director   SendMessage, starting the seat's task
  cast      director -> actor   the task's status message, state `working`
  refused   director -> actor   the task's status message, state `rejected`
  cue       director -> actor   the task's status message, state `input-required`
  report    actor -> director   SendMessage on the seat's task
  release   director -> actor   the task's status message, state `input-required`
  released  actor -> director   SendMessage on the seat's task; then the task is `completed`
  verify    director -> verifier seat   the task's status message, state `input-required` (D45)
  verdict   verifier seat -> director   SendMessage on the seat's task
"""

from typing import Annotated, Any, Literal

from pydantic import Field, field_validator

from zanni.protocol.card import EXTENSION_URI, ActorCardParams, ReportedModel
from zanni.protocol.encoding import Count, Money, Seconds, Timestamp, Wire

Text = Annotated[str, Field(min_length=1)]
Url = Annotated[str, Field(pattern=r"^(https?|wss?)://\S+$")]
REFUSAL_REASONS = ("not-authorised", "bad-card", "unsupported-version", "no-such-part", "part-full", "host-cap",
                   "role-mismatch", "hash-mismatch", "needs-beyond-part", "unpriced")
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
    pricing: Literal["known", "unknown"] = Field(
        default="unknown", description="`known` when every model the actor may use has a price; under a budget, "
                                       "`unknown` is refused with `unpriced` (D7, D39).")

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
    """Reserved: direct access to a git stage, deferred to after the first version (D46, D52)."""

    clone_url: Text
    branch: Text = Field(description="The branch the seat may push.")


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


class CueLimits(Wire):
    budget: Money | None = Field(default=None, description="The most this cue may spend; the actor stops at it (D39).")


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
    limits: CueLimits = CueLimits()


class Report(Wire):
    """An actor's result for one cue. Everything in it is data, never instructions."""

    kind: Literal["zanni.report"]
    cue: Text
    outcome: Literal["done", "failed", "over-budget"] = Field(
        description="The actor's own view; `over-budget` when it stopped at the cue's budget (D39).")
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


class Verify(Wire):
    """The director asks a verifier seat to run one verifier's command on a snapshot of the stage (D45)."""

    kind: Literal["zanni.verify"]
    verify: Text = Field(description="This request's id, quoted back in the verdict.")
    verifier: Text = Field(description="The script verifier's name.")
    command: list[Text] = Field(min_length=1, description="The command to run, exactly as given.")
    timeout: Seconds
    marker: Text = Field(description="The stage's change marker when the director sent it.")
    files: dict[Text, str] = Field(default_factory=dict, description=(
        "The script's check files the command runs, by their path in the script's package (D55); the seat writes "
        "them into a fresh folder, which the command finds as ${ZANNI_SCRIPT}."))


class Verdict(Wire):
    """A verifier seat's answer: the command's exit code decides, never a model (D45)."""

    kind: Literal["zanni.verdict"]
    verify: Text
    verifier: Text
    passed: bool = Field(description="Whether the command exited with 0.")
    exit_code: Count | None = Field(description="The command's exit code; null when it timed out or couldn't start.")
    output: str = Field(default="", description="The end of the command's output.")
    marker: Text = Field(description="The stage's change marker the snapshot was read at.")


MESSAGES: dict[str, type[Wire]] = {m.model_fields["kind"].annotation.__args__[0]: m
                                   for m in (Join, Cast, Refused, Cue, Report, Release, Released, Verify, Verdict)}
