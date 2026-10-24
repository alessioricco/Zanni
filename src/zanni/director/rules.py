"""The rules the director's tools check before acting (D33, D35, D39): plain functions over the play's state.

Each returns None when the rules allow the action, or a refusal in plain words. The director's model reads the
refusal and decides again; nothing here depends on the model's goodwill (golden rule 5).
"""

from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from zanni.director.state import PlayState
from zanni.protocol.fit import within

CENT = Decimal("0.0001")


def unreserved(state: PlayState) -> Decimal | None:
    """The budget neither spent nor reserved by a pending cue; None when the play has no budget."""
    if state.budget is None:
        return None
    return state.budget - state.spend - sum(state.reservations.values(), Decimal(0))


def cue_budget(state: PlayState, idle_seats: int, asked: Decimal | None) -> tuple[Decimal | None, str | None]:
    """A cue's budget (D39): by default the unreserved budget divided among the idle seats; the model may ask for
    less, never more. (budget, refusal)"""
    left = unreserved(state)
    round_cap = state.script.stop.budget_per_round
    if round_cap is not None:
        in_round = round_cap - state.round_spend - sum(state.reservations.values(), Decimal(0))
        left = in_round if left is None else min(left, in_round)
        if in_round <= 0:
            return None, f"this round has used its budget of ${round_cap:.2f} (stop.budget_per_round); end the round"
    if left is None:
        return None, None
    if left <= 0:
        return None, f"nothing is left of the budget to reserve (spent {state.spend_text()} of ${state.budget:.2f})"
    share = (left / max(1, idle_seats)).quantize(CENT, rounding=ROUND_DOWN)
    if asked is None:
        return share, None
    if asked <= 0:
        return None, "a cue's budget must be more than 0"
    if asked > share:
        return None, f"a cue may have at most ${share} now (the unreserved budget, shared among {idle_seats} idle seat(s))"
    return asked, None


def director_may_take_a_turn(state: PlayState) -> str | None:
    """Before each of the director's turns: the budget, then the turn cap (D33, D39)."""
    if state.budget is not None and state.spend >= state.budget:
        return "budget"
    return None


def paths_within(seat_read: list[str], seat_write: list[str], reads: list[str], writes: list[str]) -> str | None:
    """A cue's paths must be within its seat's permissions; the stage enforces them anyway (D12)."""
    for kind, wanted, rules in (("write", writes, seat_write), ("read", reads, seat_read + seat_write)):
        outside = [p for p in wanted if not within(p, rules)]
        if outside:
            return f"this seat may not {kind} {', '.join(outside)}; it may {kind}: {', '.join(rules) or 'nothing'}"
    return None


def stage_missing(root: Path, expects: list[str]) -> list[str]:
    """The script's `stage.expects` paths the stage doesn't hold."""
    return [p for p in expects if not (root / p).exists()]


def may_run_verifier(state: PlayState, name: str, writing_cues: int) -> str | None:
    if name not in state.script.verifiers:
        return f"the script has no verifier {name!r}; its verifiers are: {', '.join(state.script.verifiers) or 'none'}"
    if writing_cues:
        return (f"{writing_cues} cue(s) that write to the stage are still pending; wait for their reports first, "
                "so the verdict judges finished work")
    return None


def may_stop_done(state: PlayState, marker: int) -> str | None:
    """"Done" only with every enforced gate approved and done_when verified after the last change (D33, D35)."""
    missing = [g for g in state.enforced_gates() if state.gates.get(g) != "approved"]
    if missing:
        return f"the gate(s) {', '.join(missing)} haven't been approved; ask for them with ask_gate first"
    done_when = state.script.stop.done_when
    if done_when:
        not_yet = []
        for name in done_when:
            v = state.verdicts.get(name)
            if v is None:
                not_yet.append(f"{name} (never run)")
            elif not v.passed:
                not_yet.append(f"{name} (failed)")
            elif v.marker != marker:
                not_yet.append(f"{name} (the stage changed after it passed; run it again)")
        if not_yet:
            return f"done needs these verifiers to pass on the stage as it is now: {', '.join(not_yet)}"
        return None
    this_round = [v for v in state.verdicts.values() if v.round == state.round]
    if not this_round:
        return "the script has no done_when, so done needs at least one verifier run and passed in this round"
    failed = [v.name for v in this_round if not v.passed]
    if failed:
        return f"verifiers failed in this round: {', '.join(failed)}"
    return None


def may_cast(state: PlayState, part: str, total: int, active: int, local_files: int, local_started: int,
             has_remote: bool) -> str | None:
    """Casting `total` seats of a part: within the play's seats, and the local seats listed (D36)."""
    if part not in state.play.cast:
        return f"the play casts no part {part!r}; its parts are: {', '.join(state.play.cast)}"
    seats = state.seats_for(part)
    if not seats.min <= total <= seats.max:
        return f"{part} may have {seats} seat(s); {total} is outside that"
    if total > active and local_started >= local_files and not has_remote:
        return (f"every local seat listed for {part} is already started ({local_files}); more can only come from "
                "actors joining, and this part takes none")
    return None


def may_end_round(state: PlayState) -> str | None:
    """None when another round may start; otherwise the stop reason."""
    cap = state.script.stop.max_rounds
    if cap is not None and state.round >= cap:
        return "max-rounds"
    return None
