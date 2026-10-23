"""The `zanni` command: one command, one file. The file decides what runs."""

import argparse
import sys

from zanni import __version__
from zanni.files.check import check
from zanni.files.errors import FileErrors
from zanni.files.schemas import Lockfile, Rehearsal, RoleManifest, Script
from zanni.files.summary import summarise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zanni", description="Run what a Zanni file describes.")
    parser.add_argument("--version", action="version", version=f"zanni {__version__}")
    parser.add_argument("file", nargs="?",
                        help="an actor configuration, a play file, a role manifest, a script (SCRIPT.md), or a folder")
    args = parser.parse_args(argv)
    if args.file is None:
        parser.print_usage()
        return 2
    try:
        doc, notes = check(args.file)
    except FileErrors as e:
        print(f"{args.file} has {len(e.errors)} problem{'s' if len(e.errors) > 1 else ''}; nothing was started.",
              file=sys.stderr)
        for err in e.errors:
            print(f"  {err}", file=sys.stderr)
        return 2
    print("\n".join(summarise(doc) + notes))
    if isinstance(doc, (RoleManifest, Script, Lockfile, Rehearsal)):
        print("Valid.")
    else:
        print("Valid. Nothing was started: running files comes in a later version (see ROADMAP.md).")
    return 0
