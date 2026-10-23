"""The `zanni` command: one command, one file."""

import argparse

from zanni import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zanni", description="Run what a Zanni file describes.")
    parser.add_argument("--version", action="version", version=f"zanni {__version__}")
    parser.add_argument("file", nargs="?", help="an actor file, a play file or a role manifest (.yaml)")
    args = parser.parse_args(argv)
    if args.file is None:
        parser.print_usage()
        return 2
    print("Zanni is in early development: files can't be run yet.")
    return 0
