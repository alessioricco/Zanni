"""An actor in a play: join a director over A2A, answer each cue with a report, and be released (D21, D30).

The actor is always the A2A client. It reaches the stage through the director's MCP server with the seat's
stage token (D31), and keeps its own log on its own machine (D32).
"""

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from zanni import __version__
from zanni.actor.contract import AllModelsFailed, CueTask, McpServerSpec, ResolvedModel, StageError, StageUnavailable
from zanni.actor.roles import Role
from zanni.actor.workspace import Workspace
from decimal import Decimal

from zanni.engine.a2a_client import DirectorClient, DirectorError, NotAuthorised, Status
from zanni.engine.pricing import all_priced
from zanni.engine.run import run_cue
from zanni.engine.stage_mcp import remote_stage
from zanni.files.hashing import package_hash
from zanni.files.schemas import ActorConfiguration
from zanni.log import Log
from zanni.protocol.card import EXTENSION_URI, ActorCardParams, DirectorCardParams
from zanni.protocol.encoding import money
from zanni.protocol.messages import Cast, Cue, Refused, Release, Released, Report, Verify


class CannotJoin(Exception):
    """The director can't be joined: unreachable, not a Zanni director, or on a version this actor doesn't speak."""


@dataclass
class SeatOutcome:
    exit_code: int  # 0: released with `done`; 1: released for another reason, or lost; 2: refused (D30)
    reason: str  # the release reason, the refusal reason, or why the seat was lost
    seat: str | None = None
    reports: list[Report] = field(default_factory=list)


def cue_prompt(cue) -> str:
    """A cue as the model receives it: the instructions, then the paths and verifiers it names."""
    lines = [cue.instructions]
    if cue.reads:
        lines.append(f"Stage paths to read: {', '.join(cue.reads)}.")
    if cue.writes:
        lines.append(f"Stage paths to write: {', '.join(cue.writes)}.")
    if cue.verifiers:
        lines.append(f"Your work will be judged by: {'; '.join(cue.verifiers)}.")
    return "\n".join(lines)


def actor_card(actor: ActorConfiguration, role: Role, models: list[ResolvedModel]) -> dict:
    """The actor's Agent Card, in A2A's JSON form, built from its role and configuration (casting-extension.md)."""
    m = role.manifest
    params = ActorCardParams(
        actor=actor.name,
        role={"ref": actor.role, "hash": package_hash(role.folder), "name": m.name, "version": m.version,
              "needs": {"stage_read": m.needs.stage_read, "stage_write": m.needs.stage_write, "tools": m.needs.tools},
              "never": m.never,
              "model_needs": {"tools": m.model.needs.tools, "tier": m.model.needs.tier,
                              "context": None if m.model.needs.context is None else str(m.model.needs.context)}},
        models=[{"provider": rm.entry.provider, "model": rm.entry.model} for rm in models])
    return {"name": actor.name or m.name, "description": m.mission, "version": m.version,
            "capabilities": {"extensions": [{"uri": EXTENSION_URI, "params": params.model_dump(mode="json")}]},
            "defaultInputModes": ["application/json"], "defaultOutputModes": ["application/json"],
            "skills": [{"id": name, "name": name, "description": _skill_description(role, name), "tags": []}
                       for name in role.skills],
            "provider": {"organization": f"zanni {__version__}", "url": "https://github.com/alessioricco/Zanni"}}


def _skill_description(role: Role, name: str) -> str:
    for line in role.instructions.splitlines():
        if line.startswith(f"- `{name}`: "):
            return line.split(": ", 1)[1]
    return name


def director_params(card: dict) -> DirectorCardParams:
    """The casting extension's params on a director's card; CannotJoin if it doesn't speak this version."""
    extensions = card.get("capabilities", {}).get("extensions", [])
    ours = [e for e in extensions if e.get("uri") == EXTENSION_URI]
    if not ours:
        base = EXTENSION_URI.split("#")[0]
        other = [e["uri"] for e in extensions if e.get("uri", "").split("#")[0] == base]
        if other:
            raise CannotJoin(f"the director speaks the casting extension at {', '.join(other)}, and this actor "
                             f"speaks {EXTENSION_URI}; use a zanni version that speaks it")
        raise CannotJoin("it isn't a Zanni director: its card doesn't carry the casting extension")
    try:
        return DirectorCardParams.model_validate(ours[0].get("params", {}))
    except ValueError as e:
        raise CannotJoin(f"its card's casting params aren't valid: {e}") from None


async def play_seat(url: str, actor: ActorConfiguration, role: Role, models: list[ResolvedModel],
                    servers: list[McpServerSpec], *, join_token: str | None, log_at: Callable[[str], Path],
                    run_id: str, say: Callable[[str], None] = print, runner=run_cue,
                    part: str | None = None, workspace: Workspace | None = None) -> SeatOutcome:
    """Join the director at `url`, play the seat until it ends, and return how it ended.

    `log_at(play)` gives where the actor's own log goes (D32).
    """
    async with contextlib.AsyncExitStack() as stack:
        client = DirectorClient(url)
        stack.push_async_callback(client.close)
        try:
            director = director_params(await client.fetch_card())
        except DirectorError as e:
            raise CannotJoin(str(e)) from None
        log = Log(log_at(director.play), run_id)
        say(f"Joining the play '{director.play}' (script {director.script}) at {url}")
        try:
            # every model priced, and every tool the actor brought; under a budget, unknown is refused (D39, D53)
            priced = all_priced(models) and not any(s.unpriced for s in servers)
            pricing = "known" if priced else "unknown"
            task_id, answer = await client.join(actor_card(actor, role, models), join_token, part, pricing)
        except DirectorError as e:
            raise CannotJoin(str(e)) from None
        if isinstance(answer, Refused):
            log.event("join-refused", director=url, reason=answer.reason, message=answer.message)
            say(f"Refused: {answer.reason}: {answer.message}")
            return SeatOutcome(2, answer.reason)
        cast: Cast = answer
        log.event("joined", director=url, play=director.play, script=director.script, seat=cast.seat, part=cast.part,
                  permissions=cast.permissions.model_dump(), expires_at=cast.expires_at)
        say(f"Cast as {cast.seat} (part {cast.part}); stage at {cast.stage.mcp_url}")
        stage = await stack.enter_async_context(remote_stage(cast.stage.mcp_url, cast.stage.token))
        return await _play(client, task_id, cast, stage, role, models, servers, log, say, runner, workspace)


async def _play(client, task_id, cast, stage, role, models, servers, log, say, runner, workspace=None) -> SeatOutcome:
    interval = int(cast.heartbeat.interval)
    statuses: asyncio.Queue = asyncio.Queue()

    async def follow():  # in the background, so the seat keeps its contact while a cue runs
        try:
            async for status in client.follow(task_id, cast.seat_token, poll_every=max(1, interval / 3),
                                              give_up_after=interval * int(cast.heartbeat.misses),
                                              on_drop=lambda why: say(f"  the task's stream dropped ({why}); polling")):
                await statuses.put(status)
        except Exception as e:
            await statuses.put(e)
        await statuses.put(None)

    follower = asyncio.create_task(follow())
    reports: list[Report] = []
    answered: set[str] = set()
    reason = "lost"
    try:
        while (status := await statuses.get()) is not None:
            if isinstance(status, NotAuthorised):
                reason = "revoked"
                say(f"  the director revoked this seat: {status}")
                break
            if isinstance(status, Exception):
                reason = "lost"
                say(f"  lost the director: {status}")
                break
            message = status.message
            if isinstance(message, Cue) and status.state == "input-required" and message.cue not in answered:
                answered.add(message.cue)
                report = await _answer(message, stage, role, models, servers, cast.seat, log, say, runner, workspace)
                reports.append(report)
                await client.send(task_id, cast.seat_token, report)
            elif isinstance(message, Verify) and status.state == "input-required" and message.verify not in answered:
                from zanni.actor.verifier import run_verify

                answered.add(message.verify)
                await client.send(task_id, cast.seat_token, await run_verify(message, stage, cast.seat, log, say))
            elif isinstance(message, Release):
                reason = message.reason
                if status.state == "input-required":  # asked to stop: discard, then confirm
                    with contextlib.suppress(DirectorError):  # the director may already have revoked the seat
                        await client.send(task_id, cast.seat_token, Released(kind="zanni.released", discarded=True))
                say(f"Released ({message.reason}{': ' + message.message if message.message else ''})")
                break  # the seat is over once released: the director may stop before the task's last status
            if status.state in ("completed", "canceled", "rejected", "failed"):
                break
    finally:
        follower.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await follower
    log.event("released", seat=cast.seat, reason=reason)
    return SeatOutcome(0 if reason == "done" else 1, reason, cast.seat, reports)


class CueError(Exception):
    """A cue that couldn't run for a reason no model caused, such as a tool server that didn't start."""


async def _stage_call(operation):
    """A workspace's fill or sync: a stage that stops answering ends the cue as failed, as in a cue (D47)."""
    try:
        return await operation
    except StageError as e:
        if e.code != "unavailable":
            raise
        raise StageUnavailable(f"the stage stopped answering: {e}") from e


async def _answer(cue: Cue, stage, role: Role, models, servers, seat: str, log: Log, say, runner,
                  workspace: Workspace | None = None) -> Report:
    say(f"  cue {cue.cue}: {cue.scene}")
    log.event("cue", seat=seat, scene=cue.scene, cue=cue.cue)
    async def marker() -> str | None:
        try:
            return (await stage.changes())[1]
        except StageError as e:
            if e.code != "unavailable":
                raise
            return None

    start = await marker()
    budget = Decimal(cue.limits.budget.amount) if cue.limits.budget else None
    task = CueTask(instructions=role.instructions, skills=role.skills, prompt=cue_prompt(cue), stage=stage,
                   models=models, mcp_servers=servers, needs_tools=role.manifest.model.needs.tools, budget=budget)
    synced = None
    try:
        if start is None:
            raise StageUnavailable("the stage isn't answering")
        if workspace is not None:  # a fresh copy of what this seat may read (D52)
            await _stage_call(workspace.fill(stage))
        result, failure = await runner(task), None
        if workspace is not None and not result.over_budget:  # only a finished cue's work reaches the stage
            try:
                synced = await _stage_call(workspace.sync(stage))
            except StageUnavailable as e:  # what the model spent still counts
                result, failure = None, StageUnavailable(str(e), result.cost)
    except (AllModelsFailed, StageUnavailable) as e:
        result, failure = None, e
    except Exception as e:  # anything else, such as a tool server that couldn't start: the cue fails, the seat goes on
        first = (str(e).splitlines() or [""])[0][:300]
        log.event("cue-error", seat=seat, cue=cue.cue, error=type(e).__name__, detail=first)
        result, failure = None, CueError(f"the cue couldn't run: {type(e).__name__}: {first}")
    attempts = result.fallbacks if result else getattr(failure, "fallbacks", [])
    for f in attempts:
        log.event("fallback", seat=seat, model=f.model, reason=f.reason, detail=f.detail)
        say(f"    {f.model} failed ({f.reason}); {'trying the next model' if result or f is not attempts[-1] else 'no model left'}")
    after = await marker() if start is not None else None
    # one marker per change since the cue began; none known while the stage is away (the director's record has them)
    changes = [str(i) for i in range(int(start) + 1, int(after) + 1)] if after is not None else []
    outcome = ("over-budget" if result.over_budget else "done") if result else "failed"
    spent = result.cost if result else (failure.cost if isinstance(failure, StageUnavailable) else None)
    report = Report(kind="zanni.report", cue=cue.cue, outcome=outcome,
                    summary=result.output if result else str(failure), changes=changes,
                    cost=money(spent) if spent is not None else None,
                    models=[{"provider": result.provider, "model": result.model_name}] if result else [])
    log.event("report", seat=seat, cue=cue.cue, outcome=report.outcome, summary=report.summary, changes=changes)
    log.event("cost", seat=seat, model=result.model if result else None, amount=report.cost.amount if report.cost else None,
              input_tokens=result.input_tokens if result else None, output_tokens=result.output_tokens if result else None,
              tool_calls=result.brought_calls if result else None)
    if synced is not None:
        say(f"    workspace sent to the stage: {synced}")
        for refused in synced.refused:
            say(f"      refused: {refused}")
    if result:
        cost = f"${report.cost.amount}" if report.cost else "unknown"
        say(f"    {'stopped at its budget' if result.over_budget else 'done'} on {result.model}: "
            f"{len(result.tool_calls)} tool calls, "
            f"{result.input_tokens} in / {result.output_tokens} out tokens, cost {cost}")
    elif isinstance(failure, (StageUnavailable, CueError)):
        say(f"    failed: {failure}")
    else:
        say("    failed: every model failed")
    return report
