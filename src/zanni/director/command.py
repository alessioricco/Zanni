"""`zanni play.yaml`, or `zanni director.yaml`: run a play on this machine (D33-D39; docs/spec/play.md, "Running a play").

Everything that can be checked is checked before anything starts (exit 2): the director's configuration, the
packages against play.lock, the play against its script, the stage, the director's models and tokens. Then the
director serves its card, its stage and the owner's endpoint, starts its local seats, waits for every part's
minimum seats, and takes turns until the play stops. Exit 0 when it stopped as done; 1 when it stopped otherwise.
"""

import asyncio
import contextlib
import json
import os
import re
import secrets
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from zanni.director.casting import VERIFIER_PART, Director, PartSlot
from zanni.director.gates import Gates
from zanni.director.local import LocalSeats
from zanni.director.owner import Owner
from zanni.director.play import Production, TurnOutcome
from zanni.director.prompt import instructions
from zanni.director.rehearsal import parse_listen
from zanni.director.rules import stage_missing
from zanni.director.state import PlayState
from zanni.stage import Stage, StageError, folder_stage
from zanni.files.check import against_script, check, check_script, describe_verifiers, resolve, verifier_commands
from zanni.files.errors import FileErrors
from zanni.files.loader import load_file
from zanni.files.schemas import REMOTE_REF, ActorConfiguration, PlayFile, Script
from zanni.files.validation import validate
from zanni.log import Log

DIRECTOR_FILE = "director.yaml"
JOIN_TOKEN, OWNER_TOKEN, VERIFIER_TOKEN = "ZANNI_JOIN_TOKEN", "ZANNI_OWNER_TOKEN", "ZANNI_VERIFIER_TOKEN"
STAGE_TOKEN = "ZANNI_STAGE_TOKEN"  # the director's token for an mcp stage (D47)


class CannotStart(Exception):
    """Something to fix before the play can start, in plain words (exit 2)."""


def find_director(play_path: Path, given: Path | None) -> Path:
    """`--director <file>`, else director.yaml beside the play file; nowhere else (D34)."""
    if given is not None:
        if not given.is_file():
            raise CannotStart(f"--director {given} doesn't exist")
        return given
    beside = play_path.parent / DIRECTOR_FILE
    if beside.is_file():
        return beside
    raise CannotStart(f"no director configuration: there is no --director, and no {beside}. Write one beside the "
                      "play (role: zanni:director, play: ./play.yaml, its models and credentials); see "
                      "examples/plays/slug-kata/director.yaml")


def load_director(path: Path, play_path: Path) -> ActorConfiguration:
    doc, _ = check(path)  # its own checks: the play, the local seats, the safeguards on its credentials (D15)
    if not isinstance(doc, ActorConfiguration) or not doc.is_director:
        raise CannotStart(f"{path} isn't a director's configuration: its role must be zanni:director")
    named = (path.parent / doc.play).resolve()
    if named != play_path.resolve():
        raise CannotStart(f"{path} directs {named}, not {play_path.resolve()}; use the director configuration of "
                          "this play, or run the other play")
    return doc


def credential(director: ActorConfiguration, name: str) -> str | None:
    from zanni.actor.resolve import Unresolved, expand

    if name not in director.credentials:
        return None
    try:
        return expand(f"${{{name}}}", director.credentials)
    except Unresolved:
        return None


def part_slots(play: PlayFile, play_folder: Path, script: Script, packages) -> list[PartSlot]:
    """Who fits each part: a remote cast entry by reference and play.lock's pin; a local one by its folder's role
    name and hash (D36); both within the part's ceilings."""
    from zanni.actor.roles import load_role
    from zanni.protocol.fit import refusal, refusal_local

    slots = []
    for part, entry in play.cast.items():
        spec = script.parts[part]
        seats = entry.seats or spec.seats
        package = packages.roles[entry.role]
        if REMOTE_REF.match(entry.role):
            fit = (lambda e, s, pin: lambda card: refusal(card, e, s, pin))(entry, spec, package.pin)
        else:
            name = load_role(package.folder).manifest.name
            fit = (lambda n, h, s: lambda card: refusal_local(card, n, h, s))(name, package.pin.hash, spec)
        slots.append(PartSlot(part, fit, seats.max))
    return slots


def local_seats(director: ActorConfiguration, base: Path) -> dict[str, list[tuple[Path, str]]]:
    """Each listed file and its `name`: the only fields the director reads from them (D36). Local verifier seats
    are under the part `zanni:verifier` (D45)."""
    out = {}
    lists = {**director.seats, **({VERIFIER_PART: director.verifier_seats.local} if director.verifier_seats.local else {})}
    for part, files in lists.items():
        out[part] = []
        for file in files:
            path = (base / file).resolve()
            out[part].append((path, str(load_file(path).data.get("name") or path.stem)))
    return out


def open_stage(play: PlayFile, play_path: Path, run_id: str, stage_token: str | None = None) -> Stage:
    """The play's stage: a folder that exists, a git repository cloned onto the run's branch, or an mcp server
    (connected when the run starts, in _run)."""
    spec = play.stage
    if spec.backend == "folder":
        root = (play_path.parent / spec.path).resolve()
        if not root.is_dir():
            raise CannotStart(f"the stage folder {root} doesn't exist")
        return folder_stage(root)
    if spec.backend == "git":
        from zanni.stage.git import CannotClone, GitBackend

        url = spec.url
        if not re.match(r"^([a-z][a-z0-9+.-]*://|[^/\s]+@[^:\s]+:)", url):  # a local path, relative to the play file
            url = str((play_path.parent / url).resolve())
        clone = play_path.parent / "log" / f"{run_id}-stage"
        try:
            return Stage(GitBackend.open(url, spec.branch, clone, f"zanni/{play.name}/{run_id}"))
        except CannotClone as e:
            raise CannotStart(str(e)) from None
    if not stage_token:
        raise CannotStart(f"this play's stage is an mcp server, and {STAGE_TOKEN} isn't in the director "
                          f"configuration's `credentials` (or has no value); add {STAGE_TOKEN}: ${{{STAGE_TOKEN}}}, "
                          "with the server's token in the environment (D47)")
    from zanni.engine.stage_backend import McpBackend

    return Stage(McpBackend(spec.url, stage_token))


def trusted_verifiers(director: ActorConfiguration, base: Path) -> list[str]:
    """The names of the verifier seats the director's configuration lists: local ones by their files' names (D45)."""
    local = [name for _, name in local_seats(director, base).get(VERIFIER_PART, [])]
    return [*local, *director.verifier_seats.remote]


def run_play(play_path: Path, *, director_path: Path | None = None, update: bool = False, listen: str | None = None,
             say: Callable[[str], None] = print, build=None, interactive: bool | None = None) -> int:
    """Run the play; returns the exit code (D33): 0 done, 1 stopped otherwise, 2 couldn't start."""
    from zanni.actor.resolve import resolve_usable_models
    from zanni.director.packages import load_script, resolve_packages
    from zanni.engine.models import build_model
    from zanni.engine.pricing import all_priced
    from zanni.fetch import FetchError

    try:
        play_path = play_path.resolve()
        director_file = find_director(play_path, director_path)
        director = load_director(director_file, play_path)
        play = validate(load_file(play_path), PlayFile)
        packages = resolve_packages(play_path, play, update=update, say=say)
        if update:
            say("play.lock is up to date with the tags; run the play again to use it.")
            return 0
        script_loaded = load_file(resolve(packages.script.folder))
        script = load_script(packages.script)
        check_script(script_loaded, script)
        if errors := against_script(load_file(play_path), play, script):
            raise FileErrors(errors)
        models, skipped = resolve_usable_models(director)
        for label, reason in skipped:
            say(f"Skipping the director's {label}: {reason}")
        if not models:
            raise CannotStart("none of the director's models can be used: " + "; ".join(r for _, r in skipped))
        for rm in models:
            build_model(rm)
        if play.house_rules.budget is not None and not all_priced(models):
            raise CannotStart("this play has a budget, and the director's models aren't all priced, so its own cost "
                              "would be unknown; add `price:` to each of its model entries (D39)")
        join_token, owner_token = credential(director, JOIN_TOKEN), credential(director, OWNER_TOKEN)
        for name, value in ((JOIN_TOKEN, join_token), (OWNER_TOKEN, owner_token)):
            if not value:
                raise CannotStart(f"{name} isn't in the director configuration's `credentials` (or has no value); add "
                                  f"{name}: ${{{name}}}, and set it in the environment (D34)")
        verifier_token = credential(director, VERIFIER_TOKEN)
        if director.verifier_seats.remote and not verifier_token:
            raise CannotStart(f"the director's configuration lists remote verifier seats, and {VERIFIER_TOKEN} isn't "
                              f"in its `credentials` (or has no value); add {VERIFIER_TOKEN}: ${{{VERIFIER_TOKEN}}}, "
                              "and give those seats the same value (D45)")
        if director.verifier_seats.local and not verifier_token:
            verifier_token = secrets.token_urlsafe(32)  # for local verifier seats only: made for this run
        host, port = parse_listen(listen)
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        stage = open_stage(play, play_path, run_id, credential(director, STAGE_TOKEN))  # last: clone only when ready
        if stage.kind != "mcp" and (missing := stage_missing(stage.backend.root, script.stage.expects)):
            raise CannotStart(f"the stage doesn't hold what the script expects (stage.expects): {', '.join(missing)}")
    except FileErrors as e:
        print(f"{play_path} can't start; nothing was started.", file=sys.stderr)
        for err in e.errors:
            print(f"  {err}", file=sys.stderr)
        return 2
    except (CannotStart, FetchError, OSError) as e:
        print(f"{play_path}: {e}; nothing was started.", file=sys.stderr)
        return 2
    except Exception as e:  # a model that can't be built, an unresolvable credential: plain words, never a trace
        from zanni.actor.resolve import Unresolved
        from zanni.engine.models import ModelSetupError

        if isinstance(e, (Unresolved, ModelSetupError)):
            print(f"{play_path}: {e}; nothing was started.", file=sys.stderr)
            return 2
        raise
    prose = script_loaded.body or ""
    for line in describe_verifiers(play, script):
        say(line)
    try:
        return asyncio.run(_run(play_path, play, script, prose, director, director_file, packages, stage, run_id, models,
                                join_token, owner_token, verifier_token, host, port, say, build or build_model,
                                sys.stdin.isatty() if interactive is None else interactive))
    except KeyboardInterrupt:
        print("Stopped before the play finished; every seat was released and every local seat stopped.",
              file=sys.stderr)
        return 1


async def _run(play_path, play, script, prose, director, director_file, packages, stage, run_id, models, join_token,
               owner_token, verifier_token, host, port, say, build, interactive) -> int:
    from zanni import __version__
    from zanni.director.console import console, stdin_lines
    from zanni.director.contract import DirectorInfo
    from zanni.engine.director_agent import run_director_turn
    from zanni.engine.serve import serving

    folder = play_path.parent
    if stage.kind == "mcp":  # connect, and check what the script expects, before anything starts (exit 2)
        try:
            await stage.backend.open()
            missing = await stage.missing(script.stage.expects)
        except Exception as e:
            await stage.close()
            detail = str(e) if isinstance(e, StageError) else f"{type(e).__name__}: {e}"
            print(f"{play_path}: couldn't reach the stage's server at {play.stage.url}: {detail}; nothing was "
                  "started.", file=sys.stderr)
            return 2
        if missing:
            await stage.close()
            print(f"{play_path}: the stage doesn't hold what the script expects (stage.expects): {', '.join(missing)}"
                  "; nothing was started.", file=sys.stderr)
            return 2
    log = Log(folder / "log" / f"{run_id}.jsonl", run_id)
    state = PlayState(play, script)
    casting = Director(join_token=join_token, parts=part_slots(play, folder, script, packages),
                       stage=stage, log=log, say=say,
                       max_per_host=play.house_rules.max_seats_per_host,
                       require_pricing=play.house_rules.budget is not None, verifier_token=verifier_token,
                       verifier_seats=frozenset(trusted_verifiers(director, director_file.parent)))
    gates = Gates(state, log, play.house_rules.gate_timeout, say=say)
    production = Production(state=state, casting=casting, stage=casting.stage, log=log,
                            verifiers=verifier_commands(play, script), gates=gates, say=say)
    if director.seats or director.verifier_seats.local:
        production.local = LocalSeats(local_seats(director, director_file.parent), join_token=join_token, log=log,
                                      out_dir=folder / "log" / f"{run_id}-seats", say=say,
                                      on_exit=production.local_seat_exited, verifier_token=verifier_token)
    info = DirectorInfo(name=f"zanni director {play.name}", description=script.mission, version=__version__,
                        play=play.name, script=play.script)
    text = instructions(script, prose, play)
    tools = production.tools()

    async def turn(prompt) -> TurnOutcome:
        result = await run_director_turn(models, text, prompt, tools, build=build,
                                         spending=production.director_spending)
        return TurnOutcome(result.model, result.cost, result.requests, result.fallbacks, result.input_tokens,
                           result.output_tokens)

    log.event("run-started", play=play.name, script={"ref": play.script, "commit": packages.script.pin.commit,
                                                     "hash": packages.script.pin.hash})
    running = folder / "log" / "director.json"
    background = []
    reason, completed = "interrupted", False
    try:
        async with serving(casting, info, host, port, owner=Owner(production, owner_token)) as server:
            running.write_text(json.dumps({"url": server.url, "run": run_id, "pid": os.getpid()}) + "\n")
            where = server.url if host not in ("0.0.0.0", "::") else (
                f"http://{host}:{server.port} (actors on other machines use this machine's address, port {server.port})")
            say(f"Directing '{play.name}' ({script.name} {script.version}) at {where}; run {run_id}")
            if interactive:
                background.append(asyncio.create_task(console(gates, stdin_lines(asyncio.get_running_loop()), say)))
            if production.local is not None:
                production.local.url = server.url
                for part in play.cast:
                    await production.local.start(part, min(production.local.listed(part), state.seats_for(part).min))
                await production.local.start(VERIFIER_PART, production.local.listed(VERIFIER_PART))
            await _wait_for_minimums(production, say)
            reason, completed = await production.direct(turn)
            await production.finish()
            await _publish(production, play, completed, say)
    finally:
        for task in background:
            task.cancel()
        with contextlib.suppress(FileNotFoundError):
            running.unlink()
        if production.local is not None:
            await production.local.stop_all()
        await stage.close()
        log.event("run-stopped", reason=reason, completed=completed, spend=state.spend_text().replace("$", ""))
    verdicts = ", ".join(f"{v.name} {'passed' if v.passed else 'failed'}" for v in state.verdicts.values())
    say(f"The play {'is done' if completed else 'stopped: ' + reason}. Rounds: {state.round}; spent "
        f"{state.spend_text()}; verdicts: {verdicts or 'none'}."
        + (" (done was weakly checked: the script has no stop.done_when)" if state.weak_done else ""))
    say(f"The play's log: {log.path}")
    return 0 if completed else 1


async def _publish(production: Production, play: PlayFile, completed: bool, say) -> None:
    """A git stage's run branch, pushed at the end as the stage's `push` says (D46); otherwise, how to publish it."""
    backend = production.stage.backend
    if production.stage.kind != "git":
        return
    if completed or play.stage.push == "always":
        await production.push("the end of the run")
    else:
        say(f"The run's work is on the branch {backend.run_branch}, in {backend.root}, not pushed (push: approved, and "
            f"the play didn't finish). To publish it: {backend.push_command()}")


async def _wait_for_minimums(production: Production, say) -> None:
    """Before the first turn, every part has at least its minimum seats: local ones started, others joining."""
    state = production.state
    told = False
    while short := [p for p in state.play.cast if len(production.active_seats(p)) < state.seats_for(p).min]:
        if not told:
            say(f"Waiting for actors to join: {', '.join(short)}")
            told = True
        await asyncio.sleep(0.2)

