"""`zanni gate <play file or director URL> [approve | reject | resume] [--note …] [--another-round]` (D38, D60).

Shows the play's state, or decides a pending gate, or resumes a paused play, from any machine that can reach the
director, with the owner token from the environment (ZANNI_OWNER_TOKEN), never a flag.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

OWNER_TOKEN = "ZANNI_OWNER_TOKEN"
OWNER_PATH = "/zanni/owner"
DIRECTOR_FILE = "log/director.json"  # written beside the play's log by a running director: its URL, never a token


class CannotReach(Exception):
    pass


def director_url(target: str) -> str:
    """A director's URL, or the URL a play file's running director wrote, or else the play's `director`."""
    if target.startswith(("http://", "https://")):
        return target.rstrip("/")
    path = Path(target)
    folder = path if path.is_dir() else path.parent
    running = folder / DIRECTOR_FILE
    if running.is_file():
        return json.loads(running.read_text())["url"].rstrip("/")
    if path.is_file():
        import yaml

        director = (yaml.safe_load(path.read_text()) or {}).get("director")
        if director:
            return str(director).rstrip("/")
    raise CannotReach(f"no director is running for {target}: there is no {folder / DIRECTOR_FILE}, and the play "
                      "names no `director`; start it with zanni play.yaml, or give the director's URL")


def show(state: dict) -> list[str]:
    spend = state["spend"]
    spent = f"at least ${spend.removeprefix('at least ')}" if spend.startswith("at least") else f"${spend}"
    lines = [f"Play '{state['play']}', run {state['run']}, round {state['round']}, spent {spent}: "
             + {"running": "running", "stopped": "stopped", "gate": "waiting at a gate",
                "paused": "paused"}.get(state["state"], state["state"]) + "."]
    if state.get("gate"):
        lines.append(f"  gate: {state['gate']['name']}")
        lines += [f"  {line}" for line in state["gate"]["summary"].splitlines()]
    if state.get("paused"):
        lines.append(f"  why: {state['paused']['reason']}")
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="zanni gate", description="Show or decide a play's gate, or resume it.")
    parser.add_argument("target", help="the play file (or its folder), or the director's URL")
    parser.add_argument("action", nargs="?", choices=["approve", "reject", "resume"])
    parser.add_argument("--note", default="", help="a note for the director; required to reject")
    parser.add_argument("--another-round", action="store_true",
                        help="with approve: grant the run one more round, with the note as its input (D60)")
    args = parser.parse_args(argv)
    token = os.environ.get(OWNER_TOKEN)
    if not token:
        print(f"{OWNER_TOKEN} isn't set; set it to the play's owner token (the director's configuration has the "
              "same one). It never goes on the command line.", file=sys.stderr)
        return 2
    if args.action == "reject" and not args.note.strip():
        print("A rejection needs --note, saying what to change.", file=sys.stderr)
        return 2
    if args.another_round and args.action != "approve":
        print("--another-round goes with approve: it approves the gate and grants one more round.", file=sys.stderr)
        return 2
    try:
        url = director_url(args.target) + OWNER_PATH
        headers = {"Authorization": f"Bearer {token}"}
        if args.action is None:
            response = httpx.get(url, headers=headers, timeout=30)
        else:
            decision = {"action": args.action, "note": args.note} | ({"another_round": True} if args.another_round else {})
            response = httpx.post(url, headers=headers, json=decision, timeout=30)
    except CannotReach as e:
        print(str(e), file=sys.stderr)
        return 2
    except httpx.HTTPError as e:
        print(f"couldn't reach the director at {url}: {e}", file=sys.stderr)
        return 2
    try:
        body = response.json()
    except ValueError:
        print(f"the director at {url} answered {response.status_code}, and not as a Zanni director", file=sys.stderr)
        return 2
    if response.status_code == 401:
        print(body.get("error", "not-authorised"), file=sys.stderr)
        return 2
    if response.status_code != 200:
        print(f"Nothing decided: {body.get('error', response.status_code)}", file=sys.stderr)
        print("\n".join(show(body)) if "play" in body else "", file=sys.stderr)
        return 1
    if args.action:
        print({"approve": "Approved.", "reject": "Rejected.", "resume": "Resumed."}[args.action]
              + (" One more round granted." if args.another_round else ""))
    print("\n".join(show(body)))
    return 0
