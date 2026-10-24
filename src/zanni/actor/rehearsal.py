"""Run an actor on a rehearsal: its cues, against a fresh copy of the rehearsal's stage, with no director (D26)."""

import asyncio
import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from zanni.actor.contract import AllModelsFailed, CueResult, CueTask
from zanni.actor.mcp_config import mcp_servers
from zanni.actor.resolve import Unresolved, resolve_usable_models
from zanni.actor.roles import load_role, resolve_role_folder
from zanni.actor.stage import FolderStage
from zanni.engine.capabilities import check_tool_support
from zanni.engine.models import build_model
from zanni.engine.run import run_cue
from zanni.files.check import load_rehearsal
from zanni.files.schemas import ActorConfiguration, Rehearsal, RehearsalCue
from zanni.protocol.encoding import money
from zanni.protocol.messages import Report


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Log:
    """The run's log: one JSON object per line, in the play log's format (D18). Never holds a credential (D15)."""

    def __init__(self, path: Path, run_id: str):
        self.path, self.run_id = path, run_id
        path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event: str, **fields) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps({"ts": now(), "run": self.run_id, "event": event, **fields}) + "\n")


def cue_prompt(cue: RehearsalCue) -> str:
    lines = [cue.instructions]
    if cue.reads:
        lines.append(f"Stage paths to read: {', '.join(cue.reads)}.")
    if cue.writes:
        lines.append(f"Stage paths to write: {', '.join(cue.writes)}.")
    if cue.verifiers:
        lines.append(f"Your work will be judged by: {'; '.join(cue.verifiers)}.")
    return "\n".join(lines)


@dataclass
class RehearsalOutcome:
    run_dir: Path
    reports: list[Report]
    verdicts: list[tuple[str, bool, str]]  # (name, passed, detail)

    @property
    def passed(self) -> bool:
        return all(r.outcome == "done" for r in self.reports) and all(ok for _, ok, _ in self.verdicts)


def run_rehearsal(config_path: Path, actor: ActorConfiguration, *, say: Callable[[str], None] = print,
                  runner=run_cue, run_id: str | None = None) -> RehearsalOutcome:
    base = config_path.parent
    rehearsal_path = (base / actor.play).resolve()
    _, rehearsal = load_rehearsal(rehearsal_path)
    role = load_role(resolve_role_folder(actor.role, base))
    models, skipped = resolve_usable_models(actor)
    for label, reason in skipped:
        say(f"Skipping {label}: {reason}")
    if not models:
        raise Unresolved(skipped[0][1] if skipped else "the actor configuration lists no model")
    for rm in models:  # catch a model that can't be built, or can't do what the role needs, before anything runs
        build_model(rm)
        check_tool_support(rm, role.manifest.model.needs.tools, rm.base_url)

    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    state = Path(actor.state_dir).expanduser() if actor.state_dir else Path.home() / ".zanni/actors" / (actor.name or role.manifest.name)
    run_dir = state / "rehearsals" / rehearsal.rehearsal / run_id
    shutil.copytree(rehearsal_path.parent / rehearsal.stage, run_dir / "stage")
    stage = FolderStage(run_dir / "stage", read=role.manifest.needs.stage_read, write=role.manifest.needs.stage_write)
    log = Log(run_dir / "log.jsonl", run_id)
    seat = actor.name or role.manifest.name
    log.event("run-started", play=f"rehearsal:{rehearsal.rehearsal}", script=str(rehearsal_path))
    say(f"Rehearsal '{rehearsal.rehearsal}' with {seat} ({role.manifest.name} {role.manifest.version}); run {run_id}")

    servers = mcp_servers(role.folder, actor.credentials)
    reports: list[Report] = []
    for n, cue in enumerate(rehearsal.cues, start=1):
        cue_id = f"{rehearsal.rehearsal}-{n}"
        say(f"  cue {n}/{len(rehearsal.cues)}: {cue.scene}")
        log.event("cue", seat=seat, scene=cue.scene, cue=cue_id)
        start = stage.changes()[1]
        task = CueTask(instructions=role.instructions, skills=role.skills, prompt=cue_prompt(cue), stage=stage,
                       models=models, mcp_servers=servers, needs_tools=role.manifest.model.needs.tools)
        try:
            result: CueResult | None = asyncio.run(runner(task))
            failure = None
        except AllModelsFailed as e:
            result, failure = None, e
        attempts = (result.fallbacks if result else failure.fallbacks)
        for f in attempts:
            log.event("fallback", seat=seat, model=f.model, reason=f.reason, detail=f.detail)
            say(f"    {f.model} failed ({f.reason}); {'trying the next model' if result or f is not attempts[-1] else 'no model left'}")
        after = stage.changes()[1]
        changes = [str(i) for i in range(int(start) + 1, int(after) + 1)]  # one marker per change this cue made
        report = Report(kind="zanni.report", cue=cue_id, outcome="done" if result else "failed",
                        summary=result.output if result else str(failure), changes=changes,
                        cost=money(result.cost) if result and result.cost is not None else None,
                        models=[{"provider": result.provider, "model": result.model_name}] if result else [])
        reports.append(report)
        log.event("report", seat=seat, scene=cue.scene, summary=report.summary, changes=report.changes)
        log.event("cost", seat=seat, model=result.model if result else None,
                  amount=report.cost.amount if report.cost else None)
        if result:
            cost = f"${report.cost.amount}" if report.cost else "unknown"
            say(f"    done on {result.model}: {len(result.tool_calls)} tool calls, "
                f"{result.input_tokens} in / {result.output_tokens} out tokens, cost {cost}")
        else:
            say("    failed: every model failed")

    verdicts = []
    for check in rehearsal.verify:
        proc = subprocess.run(check.command, cwd=run_dir / "stage", capture_output=True, text=True)
        tail = (proc.stdout.strip().splitlines() or proc.stderr.strip().splitlines() or [""])[-1]
        verdicts.append((check.name, proc.returncode == 0, tail))
        log.event("verdict", scene="verify", verifier=check.name, kind="hard", passed=proc.returncode == 0, detail=tail)
        say(f"  verify {check.name}: {'passed' if proc.returncode == 0 else 'FAILED'} ({tail})")
    outcome = RehearsalOutcome(run_dir, reports, verdicts)
    log.event("run-stopped", reason="rehearsal finished")
    say(f"Rehearsal {'passed' if outcome.passed else 'FAILED'}. Stage and log: {run_dir}")
    return outcome
