"""The `zanni` command: one command, one file. The file decides what runs."""

import argparse
import sys
from pathlib import Path

from zanni import __version__
from zanni.files.check import check
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zanni", description="Run what a Zanni file describes.")
    parser.add_argument("--version", action="version", version=f"zanni {__version__}")
    parser.add_argument("--check", action="store_true", help="only validate the file; never run anything")
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
    runs_rehearsal = isinstance(doc, ActorConfiguration) and any("run with no director" in n for n in notes)
    if runs_rehearsal and not args.check:
        return rehearse(Path(args.file), doc)
    print("\n".join(summarise(doc) + notes))
    if isinstance(doc, (RoleManifest, Script, Lockfile, Rehearsal)) or args.check:
        print("Valid.")
    else:
        print("Valid. Nothing was started: running files comes in a later version (see ROADMAP.md).")
    return 0
