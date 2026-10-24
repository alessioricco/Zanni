"""Milestone 5's example plays (D51), end to end from a copy of examples/, with the director and every seat scripted
on a fake OpenAI-compatible server: the slug kata on git, with its own remote made by make-remote.py, and release
notes on the example SQLite stage server, with its verifier on a verifier seat."""

import json
import os
import shutil
import sqlite3
import subprocess
import time

import yaml

from tests.fake_openai import fake_openai
from tests.test_git_stage import branches
from tests.test_mcp_stage import free_port, start_server
from tests.test_slug_kata import EXAMPLES, PY, SLUG, TESTS, entry
from zanni.stage.git import run_git

TOKENS = {"ZANNI_JOIN_TOKEN": "join-token-fake", "ZANNI_OWNER_TOKEN": "owner-token-fake"}
NOTES = """# What's new in 2.4.0

Export your boards, archive faster, and five fixes.

## New
- Export a board to CSV. (#101)
- Press `e` to archive a card. (#104)

## Fixed
- Due dates no longer show a day early west of UTC. (#97)
- The search box keeps its focus as results load. (#103)
- Archived cards no longer count toward a column's limit. (#105)
"""


def configure(play, url, models: dict[str, str], tmp_path) -> None:
    for name, model in models.items():
        doc = yaml.safe_load((play / f"{name}.yaml").read_text())
        doc["models"] = [entry(model, url)]
        doc["credentials"] = {k: v for k, v in doc.get("credentials", {}).items() if k.startswith("ZANNI_")}
        doc["state_dir"] = str(tmp_path / "state" / name)
        (play / f"{name}.yaml").write_text(yaml.safe_dump(doc))


def run_play(play, env, approve_gate=True):
    director = subprocess.Popen([PY, "-m", "zanni", str(play / "play.yaml")], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env, stdin=subprocess.DEVNULL)
    try:
        for _ in range(450):
            shown = subprocess.run([PY, "-m", "zanni", "gate", str(play / "play.yaml")], capture_output=True,
                                   text=True, env=env)
            if "waiting at a gate" in shown.stdout or director.poll() is not None:
                break
            time.sleep(0.2)
        if approve_gate:
            subprocess.run([PY, "-m", "zanni", "gate", str(play / "play.yaml"), "approve"], capture_output=True,
                           text=True, env=env)
        out, err = director.communicate(timeout=180)
    finally:
        director.kill()
    return director.returncode, out, err


def log_of(play):
    return [json.loads(line) for line in next((play / "log").glob("2*.jsonl")).read_text().splitlines()]


def test_the_slug_kata_runs_on_git_from_a_copy(tmp_path):
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), **TOKENS}
    shutil.copytree(EXAMPLES, tmp_path / "examples")
    play = tmp_path / "examples/plays/slug-kata-git"
    made = subprocess.run([PY, "make-remote.py"], cwd=play, capture_output=True, text=True)
    assert made.returncode == 0, made.stderr
    doc = yaml.safe_load((play / "play.yaml").read_text())
    doc["verifiers"] = {
        "tests-fail": {"command": [PY, "-c", "import subprocess, sys; sys.exit(0 if subprocess.call("
                                              "[sys.executable, '-m', 'pytest', '-q', 'tests']) == 1 else 1)"]},
        "tests-pass": {"command": [PY, "-m", "pytest", "-q", "tests"]}}
    (play / "play.yaml").write_text(yaml.safe_dump(doc))
    with fake_openai() as (url, _, scripts):
        scripts["files"].update({"tests/test_slug.py": TESTS, "app/slug.py": SLUG})
        scripts["director"] = [
            [("cue", {"target": "tester", "scene": "Specify", "instructions": "Write tests/test_slug.py.",
                      "writes": ["tests/"]})],
            [("wait_for_reports", {})],
            [("cue", {"target": "coder", "scene": "Build", "instructions": "Write app/slug.py.", "writes": ["app/"]})],
            [("run_verifier", {"name": "tests-fail"})],  # the coder was refused before the gate (D48)
            [("ask_gate", {"name": "plan", "summary": "Two failing tests."})],
            [("cue", {"target": "coder", "scene": "Build", "instructions": "Write app/slug.py.", "writes": ["app/"]})],
            [("wait_for_reports", {})],
            [("run_verifier", {"name": "tests-pass"})],
            [("stop", {"reason": "done", "done": True})],
            "Done.",
        ]
        configure(play, url, {"director": "director", "tester-1": "write:tests/test_slug.py",
                              "coder-1": "write:app/slug.py", "coder-2": "write:app/words.py"}, tmp_path)
        code, out, err = run_play(play, env)
    assert code == 0, out + err
    run = log_of(play)[0]["run"]
    assert f"zanni/slug-kata-git/{run}" in branches(play / "remote.git")
    authors = run_git("log", "--format=%an", f"main..zanni/slug-kata-git/{run}", cwd=play / "remote.git").stdout.split()
    assert authors == ["coder-1", "tester-1"]
    refused = [e["reason"] for e in log_of(play) if e["event"] == "tool-refused"]
    assert any("plan must be approved in this round before coder" in r for r in refused)


def test_release_notes_run_on_the_sqlite_stage_server_with_a_verifier_seat(tmp_path):
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), **TOKENS, "ZANNI_STAGE_TOKEN": "stage-token-fake"}
    shutil.copytree(EXAMPLES, tmp_path / "examples")
    play = tmp_path / "examples/plays/release-notes"
    port = free_port()
    doc = yaml.safe_load((play / "play.yaml").read_text())
    doc["stage"]["url"] = f"http://127.0.0.1:{port}/mcp"
    (play / "play.yaml").write_text(yaml.safe_dump(doc))
    server = start_server(tmp_path, play / "stage", port, token="stage-token-fake")
    try:
        with fake_openai() as (url, _, scripts):
            scripts["files"]["notes/release-notes.md"] = NOTES
            scripts["director"] = [
                [("cue", {"target": "writer", "scene": "Draft", "instructions": "Draft notes/release-notes.md.",
                          "reads": ["changelog.md", "style.md"], "writes": ["notes/"]})],
                [("wait_for_reports", {})],
                [("cue", {"target": "editor", "scene": "Edit", "instructions": "Revise notes/release-notes.md.",
                          "writes": ["notes/"]})],
                [("wait_for_reports", {})],
                [("run_verifier", {"name": "notes-structure"})],
                [("ask_gate", {"name": "publish", "summary": "The notes cover all five changes."})],
                [("stop", {"reason": "done", "done": True})],
                "Done.",
            ]
            configure(play, url, {"director": "director", "writer-1": "write:notes/release-notes.md",
                                  "editor-1": "write:notes/release-notes.md"}, tmp_path)
            code, out, err = run_play(play, env)
    finally:
        server.kill()
    assert code == 0, out + err
    verdicts = [e for e in log_of(play) if e["event"] == "verdict"]
    assert [(v["verifier"], v["passed"], v["by"]) for v in verdicts] == [("notes-structure", True, "checker")]
    db = sqlite3.connect(tmp_path / "stage.db")
    authors = [a for (a,) in db.execute("select author from changes where path = 'notes/release-notes.md' order by id")]
    assert authors == ["writer-1", "editor-1"]
    assert not (play / "stage/notes").exists()  # the work is on the server, not in the seed folder
