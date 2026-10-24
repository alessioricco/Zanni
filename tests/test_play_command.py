"""`zanni play.yaml` end to end, in another process (D33-D39): a scripted director and scripted local seats, all on a
fake OpenAI-compatible server on loopback; a gate decided with `zanni gate`; every exit code; and a director killed
with -9 whose local seat exits through its pipe."""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from tests.fake_openai import fake_openai

EXAMPLES = Path(__file__).parents[1] / "examples"
PY = sys.executable
JOIN, OWNER = "join-token-fake", "owner-token-fake"
SCRIPT = """---
name: kata
version: 1.0.0
mission: Make the slug tests pass.
parts:
  tester:
    writes: [tests/]
  coder:
    seats: 1-2
    writes: [app/]
stage:
  expects: [backlog/round-1.md]
gates: [plan]
verifiers:
  tests-fail:
    description: every new test fails
    command: [{py}, -c, "import pathlib, sys; sys.exit(0 if pathlib.Path('tests/test_slug.py').exists() and not pathlib.Path('app/slug.py').exists() else 1)"]
  tests-pass:
    description: every test passes
    command: [{py}, -c, "import pathlib, sys; sys.exit(0 if pathlib.Path('app/slug.py').exists() else 1)"]
stop:
  max_rounds: 1
  done_when: [tests-pass]
---

The **tester** writes failing tests (`tests-fail`). **Gate: plan.** The **coder** makes them pass (`tests-pass`).
"""


def entry(model, url):
    return {"provider": "openai-compatible", "model": model, "base_url": url, "price": {"input": 1, "output": 1}}


def play_folder(tmp_path, url, *, director_model="director", coder_model="write:app/slug.py", budget=None,
                director_price=True) -> Path:
    folder = tmp_path / "kata"
    shutil.copytree(EXAMPLES / "roles/slug-tester", folder / "roles/tester")
    (folder / "roles/coder").mkdir(parents=True)
    (folder / "roles/coder/role.yaml").write_text("name: coder\nversion: 0.1.0\nmission: Make the tests pass.\n"
                                                  "needs:\n  stage_read: [backlog/, spec/, tests/]\n  stage_write: [app/]\n")
    (folder / "roles/coder/AGENTS.md").write_text("# Coder\n")
    shutil.copytree(EXAMPLES / "roles/slug-tester/rehearsals/smoke-stage", folder / "stage")
    (folder / "stage/app/slug.py").unlink()
    (folder / "script").mkdir()
    (folder / "script/SCRIPT.md").write_text(SCRIPT.format(py=PY))
    rules = {"gates": ["plan"]} | ({"budget": budget} if budget else {})
    (folder / "play.yaml").write_text(yaml.safe_dump({
        "name": "kata", "script": "./script", "stage": "./stage", "house_rules": rules,
        "cast": {"tester": {"role": "./roles/tester", "host": "local"},
                 "coder": {"role": "./roles/coder", "seats": "1-2", "host": "local"}}}))
    director = entry(director_model, url) | ({} if director_price else {"price": None})
    (folder / "director.yaml").write_text(yaml.safe_dump({
        "name": "director", "role": "zanni:director", "play": "./play.yaml", "models": [director],
        "credentials": {"ZANNI_JOIN_TOKEN": "${ZANNI_JOIN_TOKEN}", "ZANNI_OWNER_TOKEN": "${ZANNI_OWNER_TOKEN}"},
        "seats": {"tester": ["./tester-1.yaml"], "coder": ["./coder-1.yaml"]}}))
    for name, model in (("tester-1", "write:tests/test_slug.py"), ("coder-1", coder_model)):
        role = "tester" if name.startswith("tester") else "coder"
        (folder / f"{name}.yaml").write_text(yaml.safe_dump({
            "name": name, "role": f"./roles/{role}", "play": "./play.yaml", "models": [entry(model, url)],
            "state_dir": str(tmp_path / "state" / name)}))
    return folder


def env(tmp_path, **extra):
    return {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), "ZANNI_JOIN_TOKEN": JOIN,
            "ZANNI_OWNER_TOKEN": OWNER} | extra


def zanni(*args, tmp_path, timeout=120, **extra):
    return subprocess.run([PY, "-m", "zanni", *map(str, args)], capture_output=True, text=True,
                          env=env(tmp_path, **extra), timeout=timeout, stdin=subprocess.DEVNULL)


def wait_until(condition, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return
        time.sleep(0.2)
    raise TimeoutError("the condition never held")


DIRECTOR_DONE = [
    [("cue", {"target": "tester", "scene": "Specify", "instructions": "Write tests/test_slug.py.", "writes": ["tests/"]})],
    [("wait_for_reports", {})],
    [("run_verifier", {"name": "tests-fail"})],
    [("ask_gate", {"name": "plan", "summary": "The tests are written, and fail."})],
    [("cue", {"target": "coder", "scene": "Build", "instructions": "Write app/slug.py.", "writes": ["app/"]})],
    [("wait_for_reports", {})],
    [("run_verifier", {"name": "tests-pass"})],
    [("stop", {"reason": "done"})],
    "The play is done.",
]


def test_a_play_runs_to_done_with_a_gate_decided_from_another_process(tmp_path):
    with fake_openai() as (url, calls, scripts):
        scripts["director"] = list(DIRECTOR_DONE)
        folder = play_folder(tmp_path, url)
        director = subprocess.Popen([PY, "-m", "zanni", str(folder / "play.yaml")], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, env=env(tmp_path), stdin=subprocess.DEVNULL)
        try:
            def at_gate():
                shown = zanni("gate", folder / "play.yaml", tmp_path=tmp_path)
                return "waiting at a gate" in shown.stdout

            wait_until(at_gate, timeout=90)
            approved = zanni("gate", folder / "play.yaml", "approve", "--note", "go", tmp_path=tmp_path)
            out, err = director.communicate(timeout=120)
        finally:
            director.kill()
    assert approved.returncode == 0 and approved.stdout.startswith("Approved.")
    assert director.returncode == 0, out + err
    assert "verifiers, run on a snapshot of the stage" in out
    assert "The play is done. Rounds: 1;" in out and "tests-pass passed" in out
    assert (folder / "stage/app/slug.py").is_file() and (folder / "play.lock").is_file()
    assert not (folder / "log/director.json").exists()
    log = [json.loads(line) for line in next((folder / "log").glob("*.jsonl")).read_text().splitlines()]
    events = [e["event"] for e in log]
    assert events[0] == "run-started" and events[-1] == "run-stopped" and log[-1]["completed"]
    assert {"seat-started", "actor-joined", "cue", "report", "verdict", "gate-pending", "gate", "seat-released"} <= set(events)
    # each seat saw its release and exited on its own, with 0, before its pipe was closed
    assert [e["exit_code"] for e in log if e["event"] == "seat-exited"] == [0, 0]
    text = "\n".join(json.dumps(e) for e in log)
    assert JOIN not in text and OWNER not in text
    assert {"director", "write:tests/test_slug.py", "write:app/slug.py"} <= set(calls)


def test_a_director_that_stops_otherwise_exits_1(tmp_path):
    with fake_openai() as (url, _, scripts):
        scripts["director"] = [[("stop", {"reason": "stuck"})], "Stopped."]
        result = zanni(play_folder(tmp_path, url) / "play.yaml", tmp_path=tmp_path)
    assert result.returncode == 1 and "The play stopped: stuck." in result.stdout


def test_zanni_director_yaml_runs_its_play(tmp_path):
    with fake_openai() as (url, _, scripts):
        scripts["director"] = [[("stop", {"reason": "checked"})], "ok"]
        result = zanni(play_folder(tmp_path, url) / "director.yaml", tmp_path=tmp_path)
    assert result.returncode == 1 and "Directing 'kata'" in result.stdout


@pytest.mark.parametrize("change,message", [
    (lambda f: (f / "director.yaml").unlink(), "no director configuration: there is no --director, and no"),
    (lambda f: (f / "stage/backlog/round-1.md").unlink(), "the stage doesn't hold what the script expects"),
    (lambda f: (f / "director.yaml").write_text((f / "director.yaml").read_text().replace(
        "ZANNI_OWNER_TOKEN: ${ZANNI_OWNER_TOKEN}", "OTHER: ${OTHER}")), "ZANNI_OWNER_TOKEN isn't in the director"),
])
def test_what_can_be_checked_is_checked_before_anything_starts(tmp_path, change, message):
    with fake_openai() as (url, calls, _):
        folder = play_folder(tmp_path, url)
        change(folder)
        result = zanni(folder / "play.yaml", tmp_path=tmp_path)
        assert result.returncode == 2 and message in result.stderr and "nothing was started" in result.stderr
        assert calls == []


def test_an_unpriced_director_under_a_budget_doesnt_start(tmp_path):
    with fake_openai() as (url, _, _):
        folder = play_folder(tmp_path, url, budget=1.0, director_price=False)
        result = zanni(folder / "play.yaml", tmp_path=tmp_path)
    assert result.returncode == 2 and "the director's models aren't all priced" in result.stderr


def test_a_director_configuration_for_another_play_is_refused(tmp_path):
    with fake_openai() as (url, _, _):
        folder = play_folder(tmp_path, url)
        other = folder / "other.yaml"
        other.write_text((folder / "play.yaml").read_text())
        result = zanni(other, "--director", folder / "director.yaml", tmp_path=tmp_path)
    assert result.returncode == 2 and "directs" in result.stderr and "not" in result.stderr


def test_a_remote_script_that_cant_be_fetched_doesnt_start(tmp_path):
    with fake_openai() as (url, _, _):
        folder = play_folder(tmp_path, url)
        (folder / "play.yaml").write_text((folder / "play.yaml").read_text().replace(
            "script: ./script", "script: example.test/someone/kata@1.0.0"))
        config = tmp_path / "gitconfig"
        config.write_text('[url "http://127.0.0.1:9/"]\n\tinsteadOf = https://example.test/\n')
        result = zanni(folder / "play.yaml", tmp_path=tmp_path, GIT_CONFIG_GLOBAL=str(config))
    assert result.returncode == 2 and "couldn't reach https://example.test/someone/kata.git" in result.stderr


def test_a_director_killed_with_9_leaves_no_local_seat_running(tmp_path):
    with fake_openai() as (url, calls, scripts):
        scripts["director"] = [
            [("cue", {"target": "coder", "scene": "Build", "instructions": "Write.", "writes": ["app/"]})],
            [("wait_for_reports", {})], "never reached"]
        folder = play_folder(tmp_path, url, coder_model="slow")
        director = subprocess.Popen([PY, "-m", "zanni", str(folder / "play.yaml")], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=env(tmp_path), stdin=subprocess.DEVNULL)
        try:
            wait_until(lambda: "slow" in calls, timeout=90)  # the coder is mid-cue
            log = next((folder / "log").glob("*.jsonl"))
            pids = [e["pid"] for e in map(json.loads, log.read_text().splitlines()) if e["event"] == "seat-started"]
            director.send_signal(signal.SIGKILL)
            director.wait(10)

            def gone(pid):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    return True
                return False

            wait_until(lambda: all(gone(p) for p in pids), timeout=15)
        finally:
            director.kill()
    assert len(pids) == 2


def test_update_rewrites_play_lock_and_runs_nothing(tmp_path):
    with fake_openai() as (url, calls, _):
        folder = play_folder(tmp_path, url)
        first = zanni(folder / "play.yaml", "--update", tmp_path=tmp_path)
        (folder / "roles/coder/AGENTS.md").write_text("# Coder, changed\n")
        second = zanni(folder / "play.yaml", "--update", tmp_path=tmp_path)
        assert calls == []
    assert first.returncode == 0 and f"Wrote {folder / 'play.lock'}" in first.stdout
    assert second.returncode == 0 and "./roles/coder: its content changed" in second.stdout
    assert "run the play again to use it" in second.stdout


def test_a_local_seat_that_cant_join_exits_cleanly_while_watching_its_pipe(tmp_path):
    """A seat whose join fails exits 2 through the normal path, while its pipe is still open: the watch on its stdin
    mustn't make the interpreter abort at exit (it did, with SIGABRT, in milestone 4's recorded runs)."""
    with fake_openai() as (url, _, _):
        folder = play_folder(tmp_path, url)
        seat = subprocess.Popen([PY, "-m", "zanni", str(folder / "tester-1.yaml"), "--play", "http://127.0.0.1:9"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env=env(tmp_path, ZANNI_WATCH_STDIN="1"))
        try:
            seat.wait(60)  # its stdin stays open: the director is still there
            out, err = seat.stdout.read(), seat.stderr.read()
        finally:
            seat.kill()
    assert seat.returncode == 2, out + err
    assert "Fatal Python error" not in err
