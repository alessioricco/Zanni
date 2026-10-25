"""The `zanni` command: one command, one file. The file decides what runs."""

import argparse
import sys
from pathlib import Path

from zanni import __version__
from zanni.files.check import check, play_target
from zanni.files.errors import FileErrors
from zanni.files.schemas import ActorConfiguration, PlayFile, Rehearsal
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
        # os.read, not sys.stdin: a thread blocked in the buffered reader holds its lock, and the interpreter aborts
        # when it exits normally (a refused join) while that lock is held.
        while os.read(0, 1024):
            pass
        print("The director's pipe closed; stopping this seat.", file=sys.stderr, flush=True)
        sys.stdout.flush()
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


def direct(path: Path, doc, args) -> int:
    """Run a play on this machine: `zanni play.yaml`, or `zanni director.yaml` (D33, D34)."""
    from zanni.director.command import run_play

    if isinstance(doc, PlayFile):
        return run_play(path, director_path=Path(args.director) if args.director else None, update=args.update,
                        listen=args.listen, continues=args.continue_run)
    return run_play((path.parent / doc.play), director_path=path, update=args.update, listen=args.listen,
                    continues=args.continue_run)


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
                        help="with --serve, a play file or a director configuration: where the director listens "
                             "(default 127.0.0.1, a free port)")
    parser.add_argument("--play", metavar="URL_OR_FILE",
                        help="for an actor configuration: join this director or play instead of its `play` (D36)")
    parser.add_argument("--director", metavar="FILE",
                        help="for a play file: the director's configuration (default: director.yaml beside it) (D34)")
    parser.add_argument("--update", action="store_true",
                        help="for a play: re-resolve its packages' tags, rewrite play.lock, and say what changed (D37)")
    parser.add_argument("--continue", metavar="RUN_ID", dest="continue_run",
                        help="for a play: start a new run from where an earlier run of it left off (D60)")
    parser.add_argument("file", nargs="?",
                        help="an actor or director configuration, a play file, a role manifest, a script (SCRIPT.md), "
                             "a rehearsal, or a folder")
    args = parser.parse_args(argv)
    if args.file is None:
        parser.print_usage()
        return 2
    try:
        doc, notes = check(args.file)
    except FileErrors as e:
        return problems(args.file, e.errors)
    directs = isinstance(doc, PlayFile) or (isinstance(doc, ActorConfiguration) and doc.is_director)
    for name, flag, allowed, what in (
            ("--serve", args.serve, isinstance(doc, Rehearsal), "a rehearsal"),
            ("--listen", args.listen, isinstance(doc, Rehearsal) or directs,
             "a rehearsal (with --serve), a play file or a director configuration"),
            ("--director", args.director, isinstance(doc, PlayFile), "a play file"),
            ("--update", args.update, directs, "a play file or a director configuration"),
            ("--continue", args.continue_run, directs, "a play file or a director configuration"),
            ("--play", args.play, isinstance(doc, ActorConfiguration) and not doc.is_director, "an actor configuration")):
        if flag and not allowed:
            print(f"{args.file}: {name} works with {what} only; nothing was started.", file=sys.stderr)
            return 2
    if args.listen and isinstance(doc, Rehearsal) and not args.serve:
        print(f"{args.file}: --listen needs --serve; nothing was started.", file=sys.stderr)
        return 2
    if args.play:
        target = args.play if "://" in args.play else str(Path(args.play).resolve())
        doc = doc.model_copy(update={"play": target})
        notes = [f"  play: {target} (from --play)"]
    if args.serve and not args.check:
        return serve(Path(args.file), doc, args.listen)
    if directs and not args.check:
        return direct(Path(args.file), doc, args)
    if isinstance(doc, ActorConfiguration) and not args.check:
        kind, where = play_target(Path(args.file).parent, doc.play)
        if kind == "rehearsal":
            return rehearse(Path(args.file), doc)
        if kind in ("director", "play-url", "play"):
            return join(Path(args.file), doc)
        print(f"{args.file}: the play {where} doesn't exist; nothing was started.", file=sys.stderr)
        return 2
    print("\n".join(summarise(doc) + notes))
    print("Valid.")
    return 0
