"""Verifiers (D35): run in the stage folder within a timeout, logged with their source; refused during a writing cue;
a later write makes a pass stale; "done" without done_when is weakly checked, and says so."""

import asyncio
import json
import os
import sys
import time

import pytest

from tests.director_harness import kata, production
from zanni.director.play import Pending
from zanni.director.verifiers import run_command
from zanni.files.check import verifier_commands
from zanni.files.schemas import PlayVerifier
from zanni.protocol.messages import Cue

PY = sys.executable


def run(coro):
    return asyncio.run(coro)


def test_a_verifier_passes_when_its_command_exits_0(tmp_path):
    assert run(run_command([PY, "-c", "print('3 passed')"], tmp_path, 10)) == (True, "3 passed")


def test_a_failing_verifier_keeps_the_end_of_its_output(tmp_path):
    passed, detail = run(run_command([PY, "-c", "import sys; print('x' * 5000); print('1 failed'); sys.exit(1)"],
                                     tmp_path, 10))
    assert not passed and detail.endswith("1 failed") and len(detail) == 2000


def test_a_verifier_runs_in_the_stage_folder(tmp_path):
    (tmp_path / "marker.txt").write_text("here")
    assert run(run_command([PY, "-c", "print(open('marker.txt').read())"], tmp_path, 10)) == (True, "here")


def test_a_missing_command_fails_in_plain_words(tmp_path):
    passed, detail = run(run_command(["no-such-command-zanni"], tmp_path, 10))
    assert not passed and detail.startswith("couldn't start no-such-command-zanni")


def test_a_timeout_stops_the_command_and_its_children(tmp_path):
    script = "import subprocess, sys, time; p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);" \
             " open('child.pid', 'w').write(str(p.pid)); time.sleep(60)"
    start = time.monotonic()
    passed, detail = run(run_command([PY, "-c", script], tmp_path, 1))
    assert not passed and detail == "timed out after 1 s, and was stopped" and time.monotonic() - start < 10
    child = int((tmp_path / "child.pid").read_text())
    for _ in range(50):
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the verifier's child process outlived its timeout")


def test_the_plays_command_overrides_the_scripts_and_says_so(tmp_path):
    play, script, _ = kata(tmp_path)
    play = play.model_copy(update={"verifiers": {"tests-pass": PlayVerifier(command=["make"], timeout=30)}})
    commands = verifier_commands(play, script)
    assert commands["tests-pass"] == (["make"], 30, "play")
    assert commands["tests-fail"][1:] == (300, "script")


def events(tmp_path):
    return [json.loads(line) for line in (tmp_path / "log.jsonl").read_text().splitlines()]


def test_a_verdict_is_logged_with_its_source_and_goes_stale_after_a_write(tmp_path):
    play, script, stage = kata(tmp_path)
    p = production(tmp_path, play, script, stage)
    (stage / "app/slug.py").write_text("x = 1\n")
    assert run(p.run_verifier("tests-pass")).startswith("tests-pass: passed")
    verdict = [e for e in events(tmp_path) if e["event"] == "verdict"][0]
    assert verdict["verifier"] == "tests-pass" and verdict["passed"] and verdict["source"] == "script"
    assert "tests-pass: every test passes [passed]" in p.summary()
    p.stage.seat([], ["app/"], "coder-1").write("app/slug.py", "x = 2\n")
    assert "[passed, but the stage changed since]" in p.summary()
    p.state.gates["plan"] = "approved"
    assert "the stage changed after it passed; run it again" in run(p.stop("done"))


def test_a_verifier_is_refused_while_a_writing_cue_is_pending(tmp_path):
    play, script, stage = kata(tmp_path)
    p = production(tmp_path, play, script, stage)
    cue = Cue(kind="zanni.cue", cue="r1-c1", scene="Build", instructions="i", writes=["app/"])
    p.pending["r1-c1"] = Pending(cue, seat=None, writes=True)
    assert "1 cue(s) that write to the stage are still pending" in run(p.run_verifier("tests-pass"))
    p.pending["r1-c1"].writes = False  # a cue that only reads doesn't hold verifiers up
    assert run(p.run_verifier("tests-pass")).startswith("tests-pass: failed")


def test_done_without_done_when_is_weakly_checked_and_logged(tmp_path):
    play, script, stage = kata(tmp_path, gates=(), done_when=())
    p = production(tmp_path, play, script, stage)
    (stage / "app/slug.py").write_text("x = 1\n")
    assert "at least one verifier run and passed in this round" in run(p.stop("done"))
    run(p.run_verifier("tests-pass"))
    assert run(p.stop("done")) == "the play is done"
    assert p.state.weak_done and p.state.stopped == ("done", True)
    assert any(e["event"] == "warning" and "weakly checked" in e["detail"] for e in events(tmp_path))


def test_done_is_a_flag_so_a_sentence_for_the_reason_still_ends_the_play_as_done(tmp_path):
    play, script, stage = kata(tmp_path, gates=())
    p = production(tmp_path, play, script, stage)
    (stage / "app/slug.py").write_text("x = 1\n")
    run(p.run_verifier("tests-pass"))
    reason = "done: round 2 was the last backlog file, and tests-pass passed"  # what a local director wrote (D42)
    assert run(p.stop(reason, done=True)) == "the play is done" and p.state.stopped == ("done", True)
    assert [e["note"] for e in events(tmp_path) if e["event"] == "stop-note"] == [reason]
