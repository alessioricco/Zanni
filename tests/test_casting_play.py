"""Casting a whole play (D36, D39): local seats as subprocesses, recasting a lost seat and resending its cue, pricing
at join, a cue's budget enforced by the actor, reservations, unknown cost, and releasing every seat at the end."""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from tests.director_harness import EXAMPLES, TOKEN, actor, actor_runner, kata, priced, production, staged, until
from tests.fake_openai import fake_openai
from zanni.actor.contract import CueTask, ResolvedModel
from zanni.stage import folder_stage
from zanni.director.contract import DirectorInfo
from zanni.director.local import LocalSeats
from zanni.engine.run import run_cue
from zanni.engine.serve import serving
from zanni.files.schemas import ModelEntry


def events(tmp_path):
    return [json.loads(line) for line in (tmp_path / "log.jsonl").read_text().splitlines()]


# Local seats: real `zanni` subprocesses, against a fake OpenAI-compatible server

def seat_config(tmp_path, name, model, base_url) -> Path:
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump({
        "name": name, "role": "./roles/coder", "play": "./play.yaml", "state_dir": str(tmp_path / "state" / name),
        "models": [{"provider": "openai-compatible", "model": model, "base_url": base_url,
                    "price": {"input": 1, "output": 1}}]}))
    return path


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path


async def local_play(tmp_path, models: list[str], base_url, body, *, coder_seats="1-2", interval=2):
    """A production whose coder seats are local subprocesses, one per model name."""
    play, script, stage = kata(tmp_path, gates=(), coder_seats=coder_seats)
    p = production(tmp_path, play, script, stage, interval=interval)
    configs = [(seat_config(tmp_path, f"coder-{i}", m, base_url), f"coder-{i}") for i, m in enumerate(models, 1)]
    p.local = LocalSeats({"coder": configs}, join_token=TOKEN, log=p.log, out_dir=tmp_path / "seats",
                         say=lambda _: None, on_exit=p.local_seat_exited)
    info = DirectorInfo(name="d", description="t", version="0", play="kata", script="./kata")
    async with serving(p.casting, info) as server:
        p.local.url = server.url
        try:
            return await body(p)
        finally:
            await p.finish()


def test_a_local_seat_is_started_plays_its_cue_and_is_stopped_at_the_end(home):
    with fake_openai() as (url, calls, _):
        async def body(p):
            assert await p.cast("coder", 1) == "coder: 0 seat(s) cast, 1 local seat(s) starting"
            await until(lambda: len(p.active_seats("coder")) == 1, timeout=60)
            assert (await p.cue("coder", "Build", "Write app/slug.py.", writes=["app/"])).startswith("cue r1-c1 sent")
            report = await p.wait_for_reports()
            assert 'outcome="done"' in report and 'changes="1"' in report
            proc = p.local.seats["coder"][0].proc
            return proc

        proc = asyncio.run(local_play(home, ["write:app/slug.py"], url, body))
    assert proc.returncode is not None and (home / "stage/app/slug.py").is_file()
    assert "write:app/slug.py" in calls
    log = [e["event"] for e in events(home)]
    assert log.index("seat-started") < log.index("actor-joined") < log.index("seat-released") < log.index("seat-exited")
    assert list((home / "state/coder-1/plays").glob("*/*/log.jsonl"))  # the actor kept its own log (D32)


def test_cast_beyond_the_listed_local_seats_is_refused(home):
    with fake_openai() as (url, _, _):
        async def body(p):
            p.state.play.cast["coder"] = p.state.play.cast["coder"].model_copy(update={"host": "local"})
            await p.cast("coder", 1)
            await until(lambda: len(p.active_seats("coder")) == 1, timeout=60)
            return await p.cast("coder", 2)

        assert "every local seat listed for coder is already started" in asyncio.run(local_play(home, ["done"], url, body))


def test_a_released_local_seat_can_be_cast_again_for_a_later_scene(home):
    """Milestone 4's recorded runs: a director released its coders after round 1, then couldn't cast them in round 2."""
    with fake_openai() as (url, _, _):
        async def body(p):
            await p.cast("coder", 1)
            await until(lambda: len(p.active_seats("coder")) == 1, timeout=60)
            assert await p.release("coder-1", "round 1 is done") == "coder-1 released"
            again = await p.cast("coder", 1)
            await until(lambda: len(p.active_seats("coder")) == 1, timeout=60)
            sent = await p.cue("coder", "Build", "Write app/slug.py.", writes=["app/"])
            return again, sent, await p.wait_for_reports()

        again, sent, report = asyncio.run(local_play(home, ["write:app/slug.py"], url, body))
    assert again == "coder: 0 seat(s) cast, 1 local seat(s) starting"
    assert sent.startswith("cue r1-c1 sent") and 'outcome="done"' in report
    started = [e for e in events(home) if e["event"] == "seat-started"]
    assert len(started) == 2 and not [e for e in events(home) if e["event"] == "seat-not-restarted"]


class FakeProc:
    """A seat's process whose exit is seen in two steps, as asyncio does: its returncode first, its waiters later."""

    def __init__(self, pid):
        self.pid, self.returncode, self.stdin = pid, None, type("Pipe", (), {"close": lambda self: None})()
        self.exited = asyncio.Event()

    async def wait(self):
        await self.exited.wait()
        return self.returncode

    def kill(self):
        self.returncode = -9
        self.exited.set()


def test_a_released_seats_late_exit_isnt_taken_for_its_next_process_crashing(tmp_path, monkeypatch):
    """CI flake: the old process's waiters woke while its next one was being spawned, and the seat was restarted."""
    from zanni.log import Log

    async def body():
        procs, exits = [], []
        local = LocalSeats({"coder": [(tmp_path / "coder-1.yaml", "coder-1")]}, join_token=TOKEN,
                           log=Log(tmp_path / "log.jsonl", "r1"), out_dir=tmp_path / "seats", say=lambda _: None,
                           on_exit=lambda name: asyncio.sleep(0, exits.append(name)))
        local.url = "http://127.0.0.1:1"

        async def spawn(*args, **kwargs):
            if procs:  # the old process's waiters wake while the next one starts
                procs[-1].exited.set()
                for _ in range(5):
                    await asyncio.sleep(0)
            procs.append(FakeProc(len(procs) + 1))
            return procs[-1]

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        await local.start("coder", 1)
        local.released("coder-1")
        procs[0].returncode = 0  # it exited after its release; its waiters haven't woken yet
        await local.start("coder", 1)
        await asyncio.sleep(0.1)
        local.stopping = True
        procs[-1].kill()
        await asyncio.sleep(0.1)
        return exits, len(procs)

    assert asyncio.run(body()) == ([], 2)


def test_a_local_seat_exits_mid_cue_when_its_directors_pipe_closes(home):
    with fake_openai() as (url, calls, _):
        async def body(p):
            await p.cast("coder", 1)
            await until(lambda: len(p.active_seats("coder")) == 1, timeout=60)
            await p.cue("coder", "Build", "Write app/slug.py.", writes=["app/"])
            await until(lambda: "slow" in calls, timeout=30)  # the actor is mid-cue, waiting on its model
            seat = p.local.seats["coder"][0]
            seat.expected_exit = True  # as if the director died: nothing restarts it
            start = time.monotonic()
            seat.proc.stdin.close()  # what the OS does to the pipe when the director's process dies
            code = await asyncio.wait_for(seat.proc.wait(), 15)
            return code, time.monotonic() - start

        code, took = asyncio.run(local_play(home, ["slow"], url, body))
    assert code == 1 and took < 10


def test_a_seat_that_keeps_crashing_is_restarted_twice_then_left_to_joining_actors(home):
    with fake_openai() as (url, _, _):
        async def body(p):
            p.recast_wait = 0.5
            await p.cast("coder", 1)
            seat = p.local.seats["coder"][0]
            for crash in range(3):
                await until(lambda: len(p.active_seats("coder")) == 1, timeout=60)
                proc = seat.proc
                proc.send_signal(signal.SIGKILL)
                await proc.wait()
                await until(lambda: not p.active_seats("coder") and (seat.proc is not proc or crash == 2), timeout=30)
            await asyncio.sleep(1)
            return seat.restarts

        assert asyncio.run(local_play(home, ["done"], url, body)) == 2
    log = events(home)
    assert len([e for e in log if e["event"] == "seat-started"]) == 3
    assert [e["reason"] for e in log if e["event"] == "seat-not-restarted"] == ["restarted 2 times already"]


def test_the_play_flag_overrides_a_configurations_play(home):
    shutil.copytree(EXAMPLES / "roles/slug-tester", home / "roles/x")
    config = home / "actor.yaml"
    config.write_text("name: a\nrole: ./roles/x\nplay: ./missing.yaml\nmodels:\n"
                      "  - { provider: openai-compatible, model: m, base_url: 'http://127.0.0.1:9/v1' }\n")
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "ZANNI_JOIN_TOKEN": TOKEN}
    run = lambda *a: subprocess.run([sys.executable, "-m", "zanni", *a], capture_output=True, text=True, env=env,  # noqa: E731
                                    timeout=60)
    checked = run(str(config), "--play", "http://127.0.0.1:9", "--check")
    assert checked.returncode == 0 and "play: http://127.0.0.1:9 (from --play)" in checked.stdout
    joined = run(str(config), "--play", "http://127.0.0.1:9")
    assert joined.returncode == 2 and "couldn't fetch the director's card from http://127.0.0.1:9" in joined.stderr
    refused = run(str(Path(__file__).parent / "conformance/valid/play-minimal.yaml"), "--play", "http://x")
    assert refused.returncode == 2 and "--play works with an actor configuration only" in refused.stderr


# Recasting a lost seat (in process, over loopback)

def slow_runner(started: asyncio.Event):
    async def run(task):
        started.set()
        await asyncio.sleep(3600)
    return run


def test_a_seat_lost_mid_cue_is_recast_and_its_cue_resent_and_completed(tmp_path):
    play, script, stage = kata(tmp_path, gates=())
    p = production(tmp_path, play, script, stage, interval=1)

    async def body(p):
        started = asyncio.Event()
        info = DirectorInfo(name="d", description="t", version="0", play="kata", script="./kata")
        async with serving(p.casting, info) as server:
            first = asyncio.create_task(actor(server.url, tmp_path, "coder", slow_runner(started), name="coder-a"))
            await until(lambda: len(p.active_seats("coder")) == 1)
            await p.cue("coder", "Build", "Write app/slug.py.", writes=["app/"])
            await started.wait()
            first.cancel()  # the actor dies mid-cue: no more heartbeats
            second = asyncio.create_task(actor(server.url, tmp_path, "coder",
                                               actor_runner({"app/slug.py": "x = 1\n"}), name="coder-b"))
            report = await asyncio.wait_for(p.wait_for_reports(), 60)
            await p.finish()
            await asyncio.gather(first, second, return_exceptions=True)
            return report

    report = asyncio.run(body(p))
    assert 'seat="coder-2"' in report and 'cue="r1-c1-again"' in report and 'outcome="done"' in report
    assert (stage / "app/slug.py").read_text() == "x = 1\n"
    log = events(tmp_path)
    assert [e["reason"] for e in log if e["event"] == "seat-released"][0] == "no-heartbeat"
    assert [(e["cue"], e["seat"], e["was"]) for e in log if e["event"] == "cue-resent"] == [("r1-c1", "coder-2", "coder-1")]


def test_a_cue_resent_after_a_missed_deadline_gets_a_new_deadline(tmp_path):
    """A seat lost to its cue's deadline: the next seat gets as long again, not the deadline that already passed."""
    play, script, stage = kata(tmp_path, gates=())
    p = production(tmp_path, play, script, stage, interval=1)
    later = timedelta()
    real = p.casting.utcnow
    p.casting.utcnow = lambda: real() + later

    async def body(p):
        nonlocal later
        started = asyncio.Event()
        info = DirectorInfo(name="d", description="t", version="0", play="kata", script="./kata")
        async with serving(p.casting, info) as server:
            first = asyncio.create_task(actor(server.url, tmp_path, "coder", slow_runner(started), name="coder-a"))
            await until(lambda: len(p.active_seats("coder")) == 1)
            await p.cue("coder", "Build", "Write app/slug.py.", writes=["app/"], deadline_minutes=60)
            await started.wait()
            later = timedelta(minutes=61)  # the first seat misses its deadline, and is released
            write = actor_runner({"app/slug.py": "x = 1\n"})

            async def takes_a_while(task):  # long enough for the director to check the deadline
                await asyncio.sleep(3)
                return await write(task)

            second = asyncio.create_task(actor(server.url, tmp_path, "coder", takes_a_while, name="coder-b"))
            report = await asyncio.wait_for(p.wait_for_reports(), 60)
            await p.finish()
            first.cancel()
            await asyncio.gather(first, second, return_exceptions=True)
            return report

    report = asyncio.run(body(p))
    assert 'seat="coder-2"' in report and 'cue="r1-c1-again"' in report and 'outcome="done"' in report
    log = events(tmp_path)
    released = [(e["seat"], e["reason"]) for e in log if e["event"] == "seat-released"]
    assert released[0] == ("coder-1", "no-heartbeat") and ("coder-2", "no-heartbeat") not in released
    first, again = [e["deadline"] for e in log if e["event"] == "cue"]
    assert again > first  # the log shows each cue's deadline


def test_a_lost_seat_nobody_replaces_is_reported_as_lost(tmp_path):
    play, script, stage = kata(tmp_path, gates=())
    p = production(tmp_path, play, script, stage, interval=1)
    p.recast_wait = 0.5

    async def body(p):
        started = asyncio.Event()
        info = DirectorInfo(name="d", description="t", version="0", play="kata", script="./kata")
        async with serving(p.casting, info) as server:
            first = asyncio.create_task(actor(server.url, tmp_path, "coder", slow_runner(started)))
            await until(lambda: len(p.active_seats("coder")) == 1)
            await p.cue("coder", "Build", "Write.", writes=["app/"])
            await started.wait()
            first.cancel()
            report = await asyncio.wait_for(p.wait_for_reports(), 60)
            await asyncio.gather(first, return_exceptions=True)
            return report

    report = asyncio.run(body(p))
    assert 'outcome="lost"' in report and "no seat of coder took its place in time" in report
    assert p.state.stopped == ("uncastable", False)  # the coder part is below its minimum, with nobody to come (D50)


# The budget: pricing at join, a cue's budget, reservations, unknown cost (D39)

def unpriced() -> ResolvedModel:
    return ResolvedModel(ModelEntry(provider="ollama", model="local", base_url="http://127.0.0.1:9"))


def test_an_unpriced_actor_is_refused_under_a_budget_and_accepted_without_one(tmp_path):
    async def join(budget):
        folder = tmp_path / ("with" if budget else "without")
        play, script, stage = kata(folder, gates=(), budget=budget)
        p = production(folder, play, script, stage)
        p.casting.require_pricing = budget is not None
        info = DirectorInfo(name="d", description="t", version="0", play="kata", script="./kata")
        async with serving(p.casting, info) as server:
            task = asyncio.create_task(actor(server.url, folder, "coder", actor_runner({}), models=[unpriced()]))
            await until(lambda: task.done() or p.active_seats())
            await p.finish()
            return await task

    refused = asyncio.run(join(Decimal("1.00")))
    assert refused.exit_code == 2 and refused.reason == "unpriced"
    accepted = asyncio.run(join(None))
    assert accepted.seat == "coder-1" and accepted.reason == "play-stopped"


def test_an_actor_stops_at_its_cues_budget_within_one_model_call(tmp_path):
    calls = []

    def endless(messages, info):
        calls.append(1)
        return ModelResponse(parts=[ToolCallPart("stage_list", {"path": ""})])

    expensive = ResolvedModel(ModelEntry(provider="openai-compatible", model="m", base_url="http://x/v1",
                                         price={"input": 1000, "output": 1000}))  # $0.001 per token
    stage = folder_stage(tmp_path).seat(["/"], [])
    task = CueTask(instructions="i", skills={}, prompt="p", stage=stage, models=[expensive], budget=Decimal("0.10"))
    result = asyncio.run(run_cue(task, build=lambda rm: FunctionModel(endless)))
    assert result.over_budget and result.cost >= Decimal("0.10") and result.requests == len(calls) == 2
    assert result.output.startswith("Stopped at the cue's budget of $0.10")


def test_reservations_across_parallel_cues_never_exceed_the_budget(tmp_path):
    play, script, stage = kata(tmp_path, gates=(), budget=Decimal("1.00"))
    p = production(tmp_path, play, script, stage)

    async def body(p):
        hold = asyncio.Event()

        async def slow(task):
            await hold.wait()
            return await actor_runner({})(task)

        for text in ("one", "two"):
            assert (await p.cue("coder", "Build", text, writes=["app/"])).startswith("cue")
        assert sum(p.state.reservations.values()) <= Decimal("1.00")
        assert list(p.state.reservations.values()) == [Decimal("0.3333"), Decimal("0.3333")]
        assert "refused: no idle seat of coder" in await p.cue("coder", "Build", "three", writes=["app/"])
        hold.set()
        await p.wait_for_reports()
        return p.state.reservations

    actors = [("tester", actor_runner({})), ("coder", actor_runner({})), ("coder", actor_runner({}))]
    assert asyncio.run(staged(p, actors, tmp_path, body)) == {}
    budgets = [e["budget"] for e in events(tmp_path) if e["event"] == "cue"]
    assert budgets == ["0.3333", "0.3333"]


def test_a_null_cost_under_a_budget_releases_the_seat_and_the_spend_becomes_at_least(tmp_path):
    play, script, stage = kata(tmp_path, gates=(), budget=Decimal("1.00"))
    p = production(tmp_path, play, script, stage)
    p.recast_wait = 0.5

    def lying(task):
        async def run():
            return replace(await actor_runner({})(task), cost=None)  # a model the price list stopped covering
        return run()

    async def body(p):
        await p.cue("coder", "Build", "Write.", writes=["app/"])
        report = await p.wait_for_reports()
        await until(lambda: not p.active_seats("coder"))
        return report

    report = asyncio.run(staged(p, [("coder", lying)], tmp_path, body))
    assert 'cost="unknown"' in report and p.state.spend_text().startswith("at least")
    assert [e["reason"] for e in events(tmp_path) if e["event"] == "seat-released"][0] == "budget"


def test_finish_releases_every_seat_with_done_or_play_stopped(tmp_path):
    play, script, stage = kata(tmp_path, gates=())
    p = production(tmp_path, play, script, stage)

    async def body(p):
        p.stop_run("done", completed=True)
        await p.finish()
        return p.active_seats()

    assert asyncio.run(staged(p, [("tester", actor_runner({})), ("coder", actor_runner({}))], tmp_path, body)) == []
    assert {e["reason"] for e in events(tmp_path) if e["event"] == "seat-released"} == {"done"}


def test_a_local_seat_refused_at_join_isnt_restarted(home):
    """D50: a refusal such as `unpriced` won't change on a restart, so the seat is started once."""
    with fake_openai() as (url, _, _):
        async def body(p):
            p.casting.require_pricing = True
            config = p.local.seats["coder"][0].config
            doc = yaml.safe_load(config.read_text())
            doc["models"][0].pop("price")
            config.write_text(yaml.safe_dump(doc))
            await p.cast("coder", 1)
            await until(lambda: any(e["event"] == "seat-not-restarted" for e in events(home)), timeout=60)
            await asyncio.sleep(1)
            return events(home)

        log = asyncio.run(local_play(home, ["done"], url, body))
    assert [e["event"] for e in log].count("seat-started") == 1
    assert [e["exit_code"] for e in log if e["event"] == "seat-exited"] == [2]
    assert "refused at join" in next(e["reason"] for e in log if e["event"] == "seat-not-restarted")
