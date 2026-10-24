"""Run an actor on a rehearsal (D26), over the real wire: a director is started for it on loopback, the actor
joins it over A2A, and reaches the stage through the director's MCP server (D29, D31)."""

import asyncio
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from zanni import __version__
from zanni.actor.join import ready_actor, state_dir
from zanni.actor.mcp_config import mcp_servers
from zanni.actor.resolve import Unresolved
from zanni.actor.seat import play_seat
from zanni.director.contract import DirectorInfo
from zanni.director.rehearsal import RehearsalOutcome, conduct, rehearsal_director
from zanni.engine.run import run_cue
from zanni.engine.serve import serving
from zanni.files.check import load_rehearsal
from zanni.files.hashing import package_hash
from zanni.files.schemas import ActorConfiguration


def run_rehearsal(config_path: Path, actor: ActorConfiguration, *, say: Callable[[str], None] = print,
                  runner=run_cue, run_id: str | None = None) -> RehearsalOutcome:
    base = config_path.parent
    rehearsal_path = (base / actor.play).resolve()
    _, rehearsal = load_rehearsal(rehearsal_path)
    role, models = ready_actor(base, actor, say)
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = state_dir(actor, role) / "rehearsals" / rehearsal.rehearsal / run_id
    seat = actor.name or role.manifest.name
    say(f"Rehearsal '{rehearsal.rehearsal}' with {seat} ({role.manifest.name} {role.manifest.version}); run {run_id}")
    token = secrets.token_urlsafe(32)  # this run's join token: the director and the actor are both right here
    director = rehearsal_director(rehearsal, rehearsal_path, role.manifest.name, package_hash(role.folder), run_dir,
                                  run_id, join_token=token, say=lambda _: None)
    info = DirectorInfo(name=f"zanni rehearsal {rehearsal.rehearsal}",
                        description=rehearsal.description or f"The rehearsal {rehearsal.rehearsal}",
                        version=__version__, play=f"rehearsal:{rehearsal.rehearsal}", script=str(rehearsal_path))
    servers = mcp_servers(role.folder, actor.credentials)

    def quiet(line: str) -> None:  # joining a director on loopback is a detail here, not news
        if not line.startswith(("Joining", "Cast as", "Released")):
            say(line)

    async def both() -> RehearsalOutcome:
        async with serving(director, info) as server:
            conducting = asyncio.create_task(conduct(director, rehearsal, rehearsal_path, run_dir,
                                                     role.manifest.name, say))
            seat_outcome = await play_seat(server.url, actor, role, models, servers, join_token=token,
                                           log_at=lambda play: run_dir / "actor-log.jsonl", run_id=run_id,
                                           say=quiet, runner=runner)
            if seat_outcome.exit_code == 2:  # refused: the conductor is still waiting for a seat
                conducting.cancel()
                raise Unresolved(f"the rehearsal's director refused this actor: {seat_outcome.reason}")
            return await conducting

    outcome = asyncio.run(both())
    say(f"Rehearsal {'passed' if outcome.passed else 'FAILED'}. Stage and log: {run_dir}")
    return outcome
