"""Verifiers on any backend (D45): on a snapshot on the director, or on a verifier seat that runs the command with no
model and reports its exit code. Only the verifier seats the director's configuration lists, presenting the verifier
token, are trusted; an actor holding the join token can never become one."""

import asyncio
import json

from tests.director_harness import PY, TOKEN, kata, production, until
from zanni.actor.roles import load_role
from zanni.actor.seat import play_seat
from zanni.actor.verifier import ROLE_FOLDER
from zanni.director.contract import DirectorInfo
from zanni.engine.serve import serving
from zanni.files.check import verifier_commands
from zanni.files.schemas import ActorConfiguration, PlayVerifier

VERIFIER_TOKEN = "verifier-token-fake"


def events(tmp_path):
    return [json.loads(line) for line in (tmp_path / "log.jsonl").read_text().splitlines()]


def with_seat(tmp_path, runs_on="ci-box", trusted=("ci-box",)):
    """A production whose `tests-pass` runs on the verifier seat `runs_on`, trusting the names in `trusted`."""
    play, script, stage = kata(tmp_path, gates=())
    play = play.model_copy(update={"verifiers": {"tests-pass": PlayVerifier(runs_on=runs_on)}})
    p = production(tmp_path, play, script, stage)
    p.verifiers = verifier_commands(play, script)
    p.casting.verifier_token, p.casting.verifier_seats = VERIFIER_TOKEN, frozenset(trusted)
    return p


async def verifier_seat(url, tmp_path, name="ci-box", token=VERIFIER_TOKEN):
    config = ActorConfiguration.model_validate({"name": name, "role": "zanni:verifier", "play": url})
    return await play_seat(url, config, load_role(ROLE_FOLDER), [], [], join_token=token,
                           log_at=lambda play: tmp_path / f"actors/{name}.jsonl", run_id="r1", say=lambda _: None)


async def served(p, body):
    info = DirectorInfo(name="d", description="test", version="0", play=p.state.play.name, script="./kata")
    async with serving(p.casting, info) as server:
        return await body(server.url)


def test_a_verifier_runs_on_a_snapshot_and_cant_change_the_stage(tmp_path):
    play, script, stage = kata(tmp_path, gates=())
    play = play.model_copy(update={"verifiers": {"tests-pass": PlayVerifier(
        command=[PY, "-c", "import pathlib; pathlib.Path('app/slug.py').write_text('changed'); "
                           "pathlib.Path('planted.txt').write_text('x')"])}})
    p = production(tmp_path, play, script, stage)
    p.verifiers = verifier_commands(play, script)

    async def go():
        await p.stage.seat([], ["app/"], "coder-1").write("app/slug.py", "def slugify(t): return t\n")
        return await p.run_verifier("tests-pass")

    assert asyncio.run(go()).startswith("tests-pass: passed")
    assert (stage / "app/slug.py").read_text() == "def slugify(t): return t\n" and not (stage / "planted.txt").exists()
    verdict = [e for e in events(tmp_path) if e["event"] == "verdict"][0]
    assert verdict["marker"] == 1 and verdict["by"] == "director" and p.state.verdicts["tests-pass"].marker == 1


def test_a_verifier_seat_runs_the_command_and_its_exit_code_is_the_verdict(tmp_path):
    p = with_seat(tmp_path)

    async def body(url):
        seat = asyncio.create_task(verifier_seat(url, tmp_path))
        await until(lambda: p.verifier_seat("ci-box") is not None)
        failed = await p.run_verifier("tests-pass")  # no app/slug.py yet: the command exits 1
        await p.stage.seat([], ["app/"], "coder-1").write("app/slug.py", "x = 1\n")
        passed = await p.run_verifier("tests-pass")
        cast = p.verifier_seat("ci-box")
        await p.finish()
        outcome = await seat
        return failed, passed, cast, outcome

    failed, passed, cast, outcome = asyncio.run(served(p, body))
    assert failed.startswith("tests-pass: failed") and passed.startswith("tests-pass: passed")
    assert cast.stage.read_rules == ["/"] and cast.stage.write_rules == []  # it reads everything, and writes nothing
    verdicts = [e for e in events(tmp_path) if e["event"] == "verdict"]
    assert [v["by"] for v in verdicts] == ["ci-box", "ci-box"] and [v["marker"] for v in verdicts] == [0, 1]
    assert "verifier-joined" in [e["event"] for e in events(tmp_path)]
    assert outcome.reason == "play-stopped"  # released at the end, like an actor
    seat_log = [json.loads(line) for line in (tmp_path / "actors/ci-box.jsonl").read_text().splitlines()]
    assert [e["exit_code"] for e in seat_log if e["event"] == "verdict"] == ["1", "0"]


def test_a_verifier_seat_cant_write_to_the_stage(tmp_path):
    from zanni.stage import StageError

    p = with_seat(tmp_path)

    async def body(url):
        seat = asyncio.create_task(verifier_seat(url, tmp_path))
        await until(lambda: p.verifier_seat("ci-box") is not None)
        try:
            await p.verifier_seat("ci-box").stage.write("app/slug.py", "planted\n")
        except StageError as e:
            refused = e.code
        await p.finish()
        await seat
        return refused

    assert asyncio.run(served(p, body)) == "not-permitted"
    assert not (tmp_path / "stage/app/slug.py").exists()


def test_only_listed_verifier_seats_with_the_verifier_token_are_cast(tmp_path):
    p = with_seat(tmp_path)

    async def body(url):
        with_join_token = await verifier_seat(url, tmp_path, token=TOKEN)
        unlisted = await verifier_seat(url, tmp_path, name="stranger")
        return with_join_token, unlisted

    with_join_token, unlisted = asyncio.run(served(p, body))
    assert with_join_token.exit_code == 2 and with_join_token.reason == "not-authorised"
    assert unlisted.exit_code == 2 and unlisted.reason == "not-authorised"
    refusals = [e for e in events(tmp_path) if e["event"] == "join-refused"]
    assert len(refusals) == 2 and not p.casting.seats


def test_an_actor_presenting_the_verifier_token_is_refused(tmp_path):
    from tests.director_harness import actor_runner, priced

    p = with_seat(tmp_path)

    async def body(url):
        role = load_role(tmp_path / "roles/coder")
        config = ActorConfiguration.model_validate({"name": "ci-box", "role": "./roles/coder", "play": url,
                                                    "models": [{"provider": "ollama", "model": "m"}]})
        return await play_seat(url, config, role, [priced()], [], join_token=VERIFIER_TOKEN,
                               log_at=lambda play: tmp_path / "actors/x.jsonl", run_id="r1", say=lambda _: None,
                               runner=actor_runner({}))

    outcome = asyncio.run(served(p, body))
    assert outcome.exit_code == 2 and outcome.reason == "not-authorised" and not p.casting.seats


def test_a_verifier_seat_that_never_joins_fails_its_verifier_in_plain_words(tmp_path):
    p = with_seat(tmp_path)
    p.state.play = p.state.play.model_copy(update={"house_rules": p.state.play.house_rules.model_copy(
        update={"cast_timeout": 1})})
    detail = asyncio.run(p.run_verifier("tests-pass"))
    assert detail.startswith("tests-pass: failed") and "the verifier seat ci-box isn't connected" in detail
