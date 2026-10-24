"""A play's state, kept by the director's code, never in its model's context (D33). Plain data, no engine imports."""

from dataclasses import dataclass, field
from decimal import Decimal

from zanni.files.schemas import PlayFile, Script, Seats


@dataclass
class Verdict:
    name: str
    passed: bool
    detail: str
    source: str  # "script" or "play": where the command came from (D35)
    marker: int  # the stage's change marker when it ran: a later change makes it stale
    round: int


@dataclass
class Report:
    """A report as the director's model sees it: the actor's text is data (golden rule 5)."""

    cue: str
    seat: str
    part: str
    scene: str
    outcome: str  # done, failed, over-budget, or lost (the seat ended before it answered)
    summary: str
    changes: list[str]
    cost: Decimal | None


@dataclass
class PlayState:
    play: PlayFile
    script: Script
    round: int = 1
    turns: int = 0  # the director's model turns in this round
    spend: Decimal = Decimal(0)
    round_spend: Decimal = Decimal(0)
    unknown_cost: bool = False  # a cost was unknown: the spend is then "at least" (D39)
    reservations: dict[str, Decimal] = field(default_factory=dict)  # cue id -> the budget it reserves
    inbox: list[Report] = field(default_factory=list)  # reports the model hasn't seen yet
    verdicts: dict[str, Verdict] = field(default_factory=dict)  # the latest per verifier
    gates: dict[str, str] = field(default_factory=dict)  # gate -> approved, rejected or skipped
    gate_rounds: dict[str, int] = field(default_factory=dict)  # gate -> the round of its latest decision (D48)
    pending_gate: tuple[str, str] | None = None  # (name, summary) while waiting at a gate
    paused: str | None = None  # why, while every director model has failed
    stopped: tuple[str, bool] | None = None  # (reason, completed) once the run ends
    weak_done: bool = False  # "done" was checked without the script's done_when (D33)

    @property
    def budget(self) -> Decimal | None:
        return self.play.house_rules.budget

    def seats_for(self, part: str) -> Seats:
        """The seats the play may cast for a part: its cast entry's, else the script's."""
        entry = self.play.cast[part]
        return entry.seats or self.script.parts[part].seats

    def spend_text(self) -> str:
        return f"{'at least ' if self.unknown_cost else ''}${self.spend:.4f}"

    def enforced_gates(self) -> list[str]:
        return [g for g in self.script.gate_names if g in self.play.house_rules.gates]

    def gate_open(self, name: str) -> bool:
        """Approved as the gate's rhythm requires: once in the play, or in this round for `every: round` (D48)."""
        if self.gates.get(name) != "approved":
            return False
        gate = self.script.gate(name)
        return gate is None or gate.every == "play" or self.gate_rounds.get(name) == self.round

    def charge(self, amount: Decimal | None) -> None:
        if amount is None:
            self.unknown_cost = True
            return
        self.spend += amount
        self.round_spend += amount
