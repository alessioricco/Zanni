"""`zanni <actor configuration>` when `play` is a director or a play file: find the director, join, play (D30)."""

import asyncio
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

from zanni.actor.contract import ResolvedModel
from zanni.actor.mcp_config import mcp_servers
from zanni.actor.resolve import Unresolved, expand, resolve_usable_models
from zanni.actor.roles import Role, load_role, resolve_role_folder
from zanni.actor.seat import CannotJoin, SeatOutcome, play_seat
from zanni.engine.capabilities import check_tool_support
from zanni.engine.models import build_model
from zanni.engine.run import run_cue
from zanni.files.check import play_target
from zanni.files.loader import load_file
from zanni.files.schemas import ActorConfiguration, PlayFile
from zanni.files.validation import validate

JOIN_TOKEN = "ZANNI_JOIN_TOKEN"
VERIFIER_TOKEN = "ZANNI_VERIFIER_TOKEN"  # a verifier seat presents it in place of the join token (D45)


def ready_actor(base: Path, actor: ActorConfiguration, say: Callable[[str], None]) -> tuple[Role, list[ResolvedModel]]:
    """The actor's role and usable models, every model built and checked before anything starts (D27). A verifier
    seat has Zanni's built-in role, and no model (D45)."""
    if actor.is_verifier:
        from zanni.actor.verifier import ROLE_FOLDER

        return load_role(ROLE_FOLDER), []
    role = load_role(resolve_role_folder(actor.role, base))
    models, skipped = resolve_usable_models(actor)
    for label, reason in skipped:
        say(f"Skipping {label}: {reason}")
    if not models:
        raise Unresolved(skipped[0][1] if skipped else "the actor configuration lists no model")
    for rm in models:  # catch a model that can't be built, or can't do what the role needs, before anything runs
        build_model(rm)
        check_tool_support(rm, role.manifest.model.needs.tools, rm.base_url)
    return role, models


def state_dir(actor: ActorConfiguration, role: Role) -> Path:
    return Path(actor.state_dir).expanduser() if actor.state_dir else Path.home() / ".zanni/actors" / (actor.name or role.manifest.name)


def director_url(base: Path, play: str) -> str:
    """Where to join: the URL itself, or a play file's `director` (local, or fetched over http(s))."""
    kind, where = play_target(base, play)
    if kind == "director":
        return where
    if kind == "missing":
        raise CannotJoin(f"the play {where} doesn't exist")
    if kind == "play-url":
        try:
            text = httpx.get(where, timeout=30, follow_redirects=True).raise_for_status().text
            doc = PlayFile.model_validate(yaml.safe_load(text))
        except Exception as e:
            raise CannotJoin(f"couldn't read the play file at {where}: {e}") from None
    else:  # the play file's own fields only: its script is the director's business, not the actor's
        doc = validate(load_file(Path(where)), PlayFile)
    if not doc.director:
        raise CannotJoin(f"the play {doc.name} has no `director` address: it runs on its director's machine, which "
                         "starts its local seats itself (zanni play.yaml); to join it from here, use --play "
                         "<the director's URL>")
    return doc.director


def join_play(config_path: Path, actor: ActorConfiguration, *, say: Callable[[str], None] = print,
              runner=run_cue) -> SeatOutcome:
    base = config_path.parent
    url = director_url(base, actor.play)
    role, models = ready_actor(base, actor, say)
    name = VERIFIER_TOKEN if actor.is_verifier else JOIN_TOKEN
    if name not in actor.credentials and name not in os.environ:
        raise Unresolved(f"{name} isn't in the actor configuration's `credentials` or the environment; add "
                         f"it, e.g. {name}: ${{{name}}}, with the play's {'verifier' if actor.is_verifier else 'join'} "
                         "token in the environment")
    token = expand(f"${{{name}}}", actor.credentials)  # credentials first, then the environment (D36)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    state = state_dir(actor, role)

    def log_at(play: str) -> Path:
        return state / "plays" / re.sub(r"[^A-Za-z0-9._-]+", "-", play).strip("-") / run_id / "log.jsonl"

    outcome = asyncio.run(play_seat(url, actor, role, models, mcp_servers(role.folder, actor.credentials),
                                    join_token=token, log_at=log_at, run_id=run_id, say=say, runner=runner))
    if outcome.seat:
        say(f"The actor's log: {state / 'plays'}")
    return outcome
