"""D60: a play continues. The owner grants one more round when approving a gate (`zanni gate … --another-round`), and
`zanni <play> --continue <run-id>` starts a new run from where an earlier one left the stage, with the next round."""

import asyncio
import json
import os
import shutil
import subprocess
import time

import yaml

from tests.director_harness import until
from tests.fake_openai import fake_openai
from tests.test_example_plays import TOKENS, configure
from tests.test_gates import directing, zanni_gate
from tests.test_git_stage import branches
from tests.test_slug_kata import EXAMPLES, PY, SLUG, TESTS
from zanni.director import rules
from zanni.director.command import CannotStart, earlier_run
from zanni.stage.git import run_git


# Another round, at a gate

def test_approving_with_another_round_raises_the_runs_limit_and_tells_the_director(tmp_path):
    async def body(p, url):
        asked = asyncio.create_task(p.ask_gate("plan", "Round 1's tests."))
        await until(lambda: p.state.pending_gate is not None)
        rejected = await zanni_gate(url, "reject", "--note", "x", "--another-round")
        granted = await zanni_gate(url, "approve", "--note", "weights next", "--another-round")
        return rejected, granted, await asked, p.summary()

    rejected, granted, answer, summary = asyncio.run(directing(tmp_path, body))
    assert rejected[0] == 2 and "--another-round goes with approve" in rejected[2]
    assert granted[0] == 0 and granted[1].startswith("Approved. One more round granted.")
    assert answer.startswith("plan: approved: weights next. The owner granted one more round: this run may now take 3")
    assert "Round 1 of 3" in summary and "weights next" in summary
    gate = [json.loads(e) for e in (tmp_path / "log.jsonl").read_text().splitlines() if '"event": "gate"' in e][-1]
    assert (gate["decision"], gate["another_round"], gate["note"]) == ("approved", True, "weights next")


def test_another_round_needs_approve_and_a_round_limit(tmp_path):
    async def body(p, url):
        asked = asyncio.create_task(p.ask_gate("plan", "x"))
        await until(lambda: p.state.pending_gate is not None)
        problems = [p.gates.decide("reject", "no", another_round=True)]
        p.state.script = p.state.script.model_copy(update={"stop": p.state.script.stop.model_copy(
            update={"max_rounds": None})})
        problems.append(p.gates.decide("approve", "", another_round=True))
        p.gates.decide("approve")
        await asked
        return problems

    problems = asyncio.run(directing(tmp_path, body))
    assert problems == ["another round can only be granted with approve",
                        "this play has no round limit, so there is no round to add; approve without --another-round"]


def test_the_round_limit_counts_this_runs_rounds(tmp_path):
    async def body(p, url):
        s = p.state
        s.continues, s.first_round, s.round = "20261025T100000Z", 2, 2
        return s.max_rounds, rules.may_end_round(s), p.summary()

    limit, stop, summary = asyncio.run(directing(tmp_path, body))
    assert (limit, stop) == (2, None)  # round 2 of the play is this run's first: a second may follow
    assert "Round 2 (round 1 of at most 2 of this run, which continues run 20261025T100000Z" in summary


# Continuing a run that ended

def test_the_earlier_runs_last_round_comes_from_its_log(tmp_path):
    play = tmp_path / "play.yaml"
    (tmp_path / "log").mkdir()
    (tmp_path / "log/r1.jsonl").write_text("\n".join(json.dumps(e) for e in [
        {"event": "run-started", "round": 1}, {"event": "round-ended", "round": 1}, {"event": "cue"},
        {"event": "run-stopped", "round": 2}]) + "\n")
    assert earlier_run(play, "r1") == 2
    for bad in ("nope", "../r1", ""):
        try:
            earlier_run(play, bad)
        except CannotStart as e:
            assert "the play's runs are: r1" in str(e)
        else:
            raise AssertionError(bad)


def gate_waiting(play, env) -> bool:
    shown = subprocess.run([PY, "-m", "zanni", "gate", str(play / "play.yaml")], capture_output=True, text=True,
                           env=env)
    return "waiting at a gate" in shown.stdout


def direct(play, env, *args, decisions=()):
    """Run the play, answering each gate with the next decision's arguments to `zanni gate`."""
    director = subprocess.Popen([PY, "-m", "zanni", str(play / "play.yaml"), *args], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env, stdin=subprocess.DEVNULL)
    decisions = list(decisions)
    try:
        until_ = time.monotonic() + 180
        while director.poll() is None and time.monotonic() < until_:
            if decisions and gate_waiting(play, env):
                subprocess.run([PY, "-m", "zanni", "gate", str(play / "play.yaml"), *decisions.pop(0)], env=env,
                               capture_output=True, text=True)
            time.sleep(0.2)
        out, err = director.communicate(timeout=60)
    finally:
        director.kill()
    return director.returncode, out, err


def events(play, run):
    return [json.loads(line) for line in (play / "log" / f"{run}.jsonl").read_text().splitlines()]


def test_a_round_granted_at_a_gate_then_a_run_continued_on_git(tmp_path):
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), **TOKENS}
    shutil.copytree(EXAMPLES, tmp_path / "examples")
    play = tmp_path / "examples/plays/slug-kata-git"
    assert subprocess.run([PY, "make-remote.py"], cwd=play, capture_output=True).returncode == 0
    doc = yaml.safe_load((play / "play.yaml").read_text())
    doc["house_rules"]["max_rounds"] = 1  # one round, unless the owner grants another
    doc["stage"]["push"] = "always"
    doc["verifiers"] = {"tests-fail": {"command": [PY, "-c", "raise SystemExit(0)"]},
                        "tests-pass": {"command": [PY, "-m", "pytest", "-q", "tests"]}}
    (play / "play.yaml").write_text(yaml.safe_dump(doc))
    with fake_openai() as (url, _, scripts):
        scripts["files"].update({"tests/test_slug.py": TESTS, "app/slug.py": SLUG})
        scripts["director"] = [
            [("cue", {"target": "tester", "scene": "Specify", "instructions": "Write the tests.", "writes": ["tests/"]})],
            [("wait_for_reports", {})],
            [("ask_gate", {"name": "plan", "summary": "Two tests."})],  # approved with --another-round
            [("end_round", {"reason": "round 1 done"})],
            [("ask_gate", {"name": "plan", "summary": "Round 2: nothing new."})],
            [("cue", {"target": "coder", "scene": "Build", "instructions": "Write app/slug.py.", "writes": ["app/"]})],
            [("wait_for_reports", {})],
            [("run_verifier", {"name": "tests-pass"})],
            [("stop", {"reason": "done", "done": True})],
            "Done.",
            # the continued run
            [("read", {"path": "app/slug.py"})],
            [("stop", {"reason": "nothing left", "done": False})],
            "Stopped.",
        ]
        configure(play, url, {"director": "director", "tester-1": "write:tests/test_slug.py",
                              "coder-1": "write:app/slug.py", "coder-2": "write:app/words.py"}, tmp_path)
        code, out, err = direct(play, env, decisions=[("approve", "--note", "one more", "--another-round"),
                                                      ("approve",)])
        assert code == 0, out + err
        first = next(p.stem for p in (play / "log").glob("2*.jsonl"))
        log = events(play, first)
        assert [e["round"] for e in log if e["event"] == "round-ended"] == [1]
        assert log[-1]["event"] == "run-stopped" and log[-1]["round"] == 2 and log[-1]["completed"]

        refused = subprocess.run([PY, "-m", "zanni", str(play / "play.yaml"), "--continue", "20000101T000000Z"],
                                 capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        assert refused.returncode == 2 and "there is no run '20000101T000000Z'" in refused.stderr

        time.sleep(1.1)  # a new run id: run ids are to the second
        code, out, err = direct(play, env, "--continue", first)
    assert code == 1, out + err  # it stopped, not done: nothing left to do
    assert f"Continuing run {first}: this run starts with round 3" in out
    second = max(p.stem for p in (play / "log").glob("2*.jsonl"))
    started = events(play, second)[0]
    assert (started["event"], started["continues"], started["round"]) == ("run-started", first, 3)
    earlier, later = f"zanni/slug-kata-git/{first}", f"zanni/slug-kata-git/{second}"
    assert {earlier, later} <= set(branches(play / "remote.git"))  # pushed to the play's remote, not the old clone
    ancestry = run_git("merge-base", "--is-ancestor", earlier, later, cwd=play / "remote.git")
    assert ancestry.returncode == 0  # the new run's branch starts from the earlier run's work
