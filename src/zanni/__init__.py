"""Zanni: an engine for teams of AI personas."""

import argparse

__version__ = "0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(prog="zanni")
    parser.add_argument("--version", action="version", version=f"zanni {__version__}")
    parser.parse_args()
    print("Zanni is in early development. Follow https://github.com/alessioricco/zanni")