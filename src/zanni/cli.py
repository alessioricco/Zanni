"""The `zanni` command: one command, one file. The file decides what runs."""

import argparse
import sys
from pathlib import Path

from zanni import __version__
from zanni.files.check import check, play_target
from zanni.files.errors import FileErrors
from zanni.files.schemas import ActorConfiguration, Lockfile, Rehearsal, RoleManifest, Script
from zanni.files.summary import summarise


def problems(file: str, errors: list) -> int:
    print(f"{file} has {len(errors)} problem{'s' if len(errors) > 1 else ''}; nothing was started.", file=sys.stderr)
    for err in errors:
        print(f"  {err}", file=sys.stderr)
    return 2


def rehearse(path: Path, actor: ActorConfiguration) -> int:
    """Run the rehearsal an actor configuration points at (D26). 0 if it passed, 1 if not, 2 if it couldn't start."""
    from zanni.actor.rehearsal import run_rehearsal  # imports the engine only when something runs
    from zanni.actor.resolve import Unresolved
    from zanni.engine.models import ModelSetupError

    try:
        outcome = run_rehearsal(path, actor)
    except FileErrors as e:
        return problems(str(path), e.errors)
    except (Unresolved, ModelSetupError) as e:
        print(f"{path}: {e}; nothing was started.", file=sys.stderr)
        return 2
    return 0 if outcome.passed else 1


WATCH_STDIN = "ZANNI_WATCH_STDIN"  # set by a director for its local seats: exit when its pipe closes (D36)


def exit_with_stdin() -> None:
    """A local seat exits as soon as its director's pipe (our stdin) closes, even mid-cue: no orphan keeps spending."""
    import os
    import threading

    def watch():
        while sys.stdin.buffer.read(1024):
            pass
        print("The director's pipe closed; stopping this seat.", file=sys.stderr, flush=True)
        os._exit(1)

    threading.Thread(target=watch, daemon=True, name="zanni-director-pipe").start()


def join(path: Path, actor: ActorConfiguration) -> int:
    """Join the director an actor configuration's `play` names (D30). 0 if released with done, 1 if not, 2 if
    refused or it couldn't start."""
    import os

    from zanni.actor.join import join_play
    from zanni.actor.resolve import Unresolved
    from zanni.actor.seat import CannotJoin
    from zanni.engine.models import ModelSetupError

    if os.environ.pop(WATCH_STDIN, None) == "1":
        exit_with_stdin()
    try:
        outcome = join_play(path, actor)
    except FileErrors as e:
        return problems(str(path), e.errors)
    except (Unresolved, ModelSetupError) as e:
        print(f"{path}: {e}; nothing was started.", file=sys.stderr)
        return 2
    except CannotJoin as e:
        print(f"{path}: couldn't join: {e}", file=sys.stderr)
        return 2
    return outcome.exit_code


def serve(path: Path, rehearsal: Rehearsal, listen: str | None) -> int:
    """Serve a rehearsal to an actor anywhere (D29). 0 if it passed, 1 if not, 2 if it couldn't start."""
    import os

    from zanni.director.rehearsal import CannotServe, serve_rehearsal

    try:
        outcome = serve_rehearsal(path.resolve(), rehearsal, listen=listen, join_token=os.environ.get("ZANNI_JOIN_TOKEN"))
    except FileErrors as e:
        return problems(str(path), e.errors)
    except (CannotServe, OSError) as e:
        print(f"{path}: {e}; nothing was started.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Stopped before the rehearsal finished.", file=sys.stderr)
        return 1
    return 0 if outcome.passed else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["gate"]:  # zanni gate <play or director URL> [approve | reject | resume] (D38)
        from zanni.gate import main as gate

        return gate(argv[1:])
    parser = argparse.ArgumentParser(prog="zanni", description="Run what a Zanni file describes.")
    parser.add_argument("--version", action="version", version=f"zanni {__version__}")
    parser.add_argument("--check", action="store_true", help="only validate the file; never run anything")
    parser.add_argument("--serve", action="store_true",
                        help="serve a rehearsal to an actor on this machine or another (D29)")
    parser.add_argument("--listen", metavar="HOST:PORT",
                        help="with --serve: where the director listens (default 127.0.0.1, a free port)")
    parser.add_argument("--play", metavar="URL_OR_FILE",
                        help="for an actor configuration: join this director or play instead of its `play` (D36)")
    parser.add_argument("file", nargs="?",
                        help="an actor configuration, a play file, a role manifest, a script (SCRIPT.md), "
                             "a rehearsal, or a folder")
    args = parser.parse_args(argv)
    if args.file is None:
        parser.print_usage()
        return 2
    try:
        doc, notes = check(args.file)
    except FileErrors as e:
        return problems(args.file, e.errors)
    if (args.serve or args.listen) and not isinstance(doc, Rehearsal):
        print(f"{args.file}: --serve and --listen work with a rehearsal only; nothing was started.", file=sys.stderr)
        return 2
    if args.listen and not args.serve:
        print(f"{args.file}: --listen needs --serve; nothing was started.", file=sys.stderr)
        return 2
    if args.play:
        if not isinstance(doc, ActorConfiguration) or doc.is_director:
            print(f"{args.file}: --play overrides an actor configuration's `play` only; nothing was started.",
                  file=sys.stderr)
            return 2
        target = args.play if "://" in args.play else str(Path(args.play).resolve())
        doc = doc.model_copy(update={"play": target})
        notes = [f"  play: {target} (from --play)"]
    if args.serve and not args.check:
        return serve(Path(args.file), doc, args.listen)
    if isinstance(doc, ActorConfiguration) and not args.check:
        kind, where = play_target(Path(args.file).parent, doc.play)
        if kind == "rehearsal":
            return rehearse(Path(args.file), doc)
        if kind in ("director", "play-url", "play"):
            return join(Path(args.file), doc)
        print(f"{args.file}: the play {where} doesn't exist; nothing was started.", file=sys.stderr)
        return 2
    print("\n".join(summarise(doc) + notes))
    if isinstance(doc, (RoleManifest, Script, Lockfile, Rehearsal)) or args.check:
        print("Valid.")
    else:
        print("Valid. Nothing was started: running files comes in a later version (see ROADMAP.md).")
    return 0
