"""The director's side of a rehearsal (D29): one part, the role that holds it; cues from the file; then verify."""

import secrets
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from zanni.actor.stage import FolderStage
from zanni.director.casting import Director, PartSlot, SeatLost
from zanni.files.schemas import Rehearsal
from zanni.log import Log
from zanni.protocol.card import ActorCardParams
from zanni.protocol.messages import Cue, Report


def role_part(name: str, role_hash: str) -> PartSlot:
    """A rehearsal's one part: an actor fits if it plays a role of that name, with that content hash."""

    def fit(card: ActorCardParams) -> tuple[str, str] | None:
        if card.role.name != name:
            return "role-mismatch", f"this rehearsal is for the role {name}, and the actor plays {card.role.name}"
        if card.role.hash != role_hash:
            return "hash-mismatch", (f"the actor's {name} has hash {card.role.hash}, and this rehearsal's package "
                                     f"has {role_hash}: they are different versions of the role")
        return None

    return PartSlot(name, fit, seats=1)


@dataclass
class RehearsalOutcome:
    run_dir: Path
    reports: list[Report] = field(default_factory=list)
    verdicts: list[tuple[str, bool, str]] = field(default_factory=list)  # (name, passed, detail)
    lost: str | None = None  # why the seat ended early, if it did

    @property
    def passed(self) -> bool:
        return (self.lost is None and all(r.outcome == "done" for r in self.reports)
                and all(ok for _, ok, _ in self.verdicts))


def rehearsal_director(rehearsal: Rehearsal, rehearsal_path: Path, role_name: str, role_hash: str, run_dir: Path,
                       run_id: str, *, join_token: str | None = None, say: Callable[[str], None] = print,
                       **settings) -> Director:
    """Copy the rehearsal's stage fresh into `run_dir/stage`, and make the director that will serve it."""
    shutil.copytree(rehearsal_path.parent / rehearsal.stage, run_dir / "stage")
    return Director(join_token=join_token or secrets.token_urlsafe(32), parts=[role_part(role_name, role_hash)],
                    stage=FolderStage(run_dir / "stage", [], []), log=Log(run_dir / "log.jsonl", run_id), say=say,
                    **settings)


async def conduct(director: Director, rehearsal: Rehearsal, rehearsal_path: Path, run_dir: Path, part: str,
                  say: Callable[[str], None] = print) -> RehearsalOutcome:
    """Wait for the actor, give it every cue in order, release it, then run the `verify` commands."""
    outcome = RehearsalOutcome(run_dir)
    director.log.event("run-started", play=f"rehearsal:{rehearsal.rehearsal}", script=str(rehearsal_path))
    seat = await director.wait_for_seat(part)
    try:
        for n, c in enumerate(rehearsal.cues, start=1):
            cue = Cue(kind="zanni.cue", cue=f"{rehearsal.rehearsal}-{n}", scene=c.scene, instructions=c.instructions,
                      reads=c.reads, writes=c.writes, verifiers=c.verifiers)
            outcome.reports.append(await director.cue(seat, cue))
        await director.release(seat, "done")
    except SeatLost as e:
        outcome.lost = e.reason
        say(f"  the seat {e.seat} was lost: {e.reason}")
    for check in rehearsal.verify:
        proc = subprocess.run(check.command, cwd=run_dir / "stage", capture_output=True, text=True)
        tail = (proc.stdout.strip().splitlines() or proc.stderr.strip().splitlines() or [""])[-1]
        outcome.verdicts.append((check.name, proc.returncode == 0, tail))
        director.log.event("verdict", scene="verify", verifier=check.name, kind="hard", passed=proc.returncode == 0,
                           detail=tail)
        say(f"  verify {check.name}: {'passed' if proc.returncode == 0 else 'FAILED'} ({tail})")
    director.log.event("run-stopped", reason="rehearsal finished" if outcome.lost is None else f"seat lost: {outcome.lost}")
    return outcome
