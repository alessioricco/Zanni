"""An actor joining a director over A2A on loopback (D21, D29–D32), with scripted models instead of real ones."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from zanni.actor.roles import load_role
from zanni.actor.seat import CannotJoin, actor_card, director_params, play_seat
from zanni.director.contract import DirectorInfo
from zanni.director.rehearsal import conduct, rehearsal_director
from zanni.engine.a2a_client import DirectorClient
from zanni.engine.run import run_cue
from zanni.engine.serve import serving
from zanni.files.check import check, load_rehearsal
from zanni.files.hashing import package_hash
from zanni.protocol.card import EXTENSION_URI, ActorCardParams

EXAMPLES = Path(__file__).parents[1] / "examples"
TWO_CUES = """rehearsal: two
stage: ./smoke-stage
cues:
  - scene: Specify
    instructions: Write tests/a.py.
  - scene: Review
    instructions: Write tests/b.py.
"""
INFO = DirectorInfo(name="test", description="A test director", version="0", play="rehearsal:two", script="two.yaml")


def writer():
    """A scripted model: each cue writes the next file (tests/a.py, then tests/b.py), then reports."""
    files, turns = iter("ab"), []

    def respond(messages, info):
        if not turns:
            name = next(files)
            turns.extend([lambda: [ToolCallPart("stage_write", {"path": f"tests/{name}.py", "content": "x"})],
                          lambda: [TextPart("Wrote it.")]])
        return ModelResponse(parts=turns.pop(0)())

    return FunctionModel(respond, model_name="scripted")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")  # never contacted: the model is scripted
    shutil.copytree(EXAMPLES / "roles", tmp_path / "roles")
    (tmp_path / "roles/slug-tester/rehearsals/two.yaml").write_text(TWO_CUES)
    config = tmp_path / "actor.yaml"
    config.write_text((EXAMPLES / "slug-tester.yaml").read_text().replace(
        "play: ./roles/slug-tester/rehearsals/smoke.yaml", "play: ./roles/slug-tester/rehearsals/two.yaml"))
    actor, _ = check(config)
    role = load_role(tmp_path / "roles/slug-tester")
    rehearsal_path = tmp_path / "roles/slug-tester/rehearsals/two.yaml"
    _, rehearsal = load_rehearsal(rehearsal_path)
    from zanni.actor.resolve import resolve_usable_models
    models, _ = resolve_usable_models(actor)
    return tmp_path, actor, role, rehearsal, rehearsal_path, models


def run_seat(setup, *, token="join-token-fake", director_token="join-token-fake", role_hash=None, interval=30,
             act=None):
    tmp_path, actor, role, rehearsal, rehearsal_path, models = setup
    run_dir = tmp_path / "run"
    director = rehearsal_director(rehearsal, rehearsal_path, role.manifest.name, role_hash or package_hash(role.folder),
                                  run_dir, "r1", join_token=director_token, heartbeat_interval=interval,
                                  heartbeat_misses=1)
    model = writer()
    lines: list[str] = []

    async def go():
        async with serving(director, INFO) as server:
            conducting = asyncio.create_task(conduct(director, rehearsal, rehearsal_path, run_dir, "slug-tester",
                                                     lines.append))
            if act is not None:
                return await act(server, director, conducting), None
            seat = await play_seat(server.url, actor, role, models, [], join_token=token,
                                   log_at=lambda play: run_dir / "actor-log.jsonl", run_id="r1", say=lines.append,
                                   runner=lambda t: run_cue(t, build=lambda rm: model))
            if seat.exit_code == 2:
                conducting.cancel()
                return seat, None
            return seat, await conducting

    seat, outcome = asyncio.run(asyncio.wait_for(go(), 60))
    return seat, outcome, run_dir, lines


def log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_an_actor_joins_answers_two_cues_and_is_released(setup):
    seat, outcome, run_dir, lines = run_seat(setup)
    assert seat.exit_code == 0 and seat.reason == "done" and seat.seat == "slug-tester-1"
    assert [r.cue for r in seat.reports] == ["two-1", "two-2"] and outcome.passed
    assert [r.changes for r in outcome.reports] == [["1"], ["2"]]
    assert (run_dir / "stage/tests/a.py").read_text() == "x" and (run_dir / "stage/tests/b.py").read_text() == "x"
    director_log = (run_dir / "log.jsonl").read_text()
    actor_log = (run_dir / "actor-log.jsonl").read_text()
    for text in (director_log, actor_log):
        keys = {k for line in text.splitlines() for k in json.loads(line)}
        assert not {k for k in keys if "token" in k} - {"input_tokens", "output_tokens"}  # never a token (D24)
        assert "join-token-fake" not in text
    own = log(run_dir / "actor-log.jsonl")
    assert own[0]["event"] == "joined" and own[0]["permissions"]["write"] == ["tests/"]
    assert [e["event"] for e in own][1:] == ["cue", "report", "cost", "cue", "report", "cost", "released"]


def test_a_wrong_join_token_is_refused_and_logged_by_the_actor(setup):
    seat, _, run_dir, lines = run_seat(setup, token="not-the-token")
    assert seat.exit_code == 2 and seat.reason == "not-authorised"
    assert log(run_dir / "actor-log.jsonl")[-1]["event"] == "join-refused"
    assert log(run_dir / "log.jsonl")[-1] == log(run_dir / "log.jsonl")[-1] | {"event": "join-refused"}


def test_another_version_of_the_role_is_refused_with_hash_mismatch(setup):
    seat, _, _, _ = run_seat(setup, role_hash="sha256:" + "0" * 64)
    assert seat.exit_code == 2 and seat.reason == "hash-mismatch"


def test_the_actor_refuses_a_director_on_another_version():
    card = {"capabilities": {"extensions": [{"uri": EXTENSION_URI.replace("#v4", "#v5"), "params": {}}]}}
    with pytest.raises(CannotJoin, match="#v4"):
        director_params(card)
    with pytest.raises(CannotJoin, match="isn't a Zanni director"):
        director_params({"capabilities": {"extensions": []}})


def test_the_actors_card_carries_its_role_and_hash(setup):
    tmp_path, actor, role, _, _, models = setup
    card = actor_card(actor, role, models)
    params = ActorCardParams.model_validate(card["capabilities"]["extensions"][0]["params"])
    assert params.role.ref == "./roles/slug-tester" and params.role.hash == package_hash(role.folder)
    assert params.actor == "slug-tester-1" and params.models[0].model == "qwen3.8:27b"  # self-reported (D11)
    assert [s["id"] for s in card["skills"]] == ["write-test"]


def test_an_actor_that_stops_answering_loses_its_seat(setup):
    """The actor joins, then goes silent (no stream, no polling): the director ends the seat and revokes it."""

    async def silent(server, director, conducting):
        _, actor, role, _, _, models = setup
        client = DirectorClient(server.url)
        await client.fetch_card()
        task_id, cast = await client.join(actor_card(actor, role, models), "join-token-fake")
        outcome = await asyncio.wait_for(conducting, 20)  # the conductor's cue fails when the seat is lost
        problem = director.authorise(cast.seat_token, task_id)
        status = await asyncio.wait_for(_last_status(client, task_id, cast.seat_token), 5)
        await client.close()
        return outcome, problem, status

    (outcome, problem, status), _, run_dir, _ = run_seat(setup, interval=1, act=silent)
    assert outcome.lost == "no-heartbeat" and not outcome.passed
    assert "revoked" in problem
    assert status == "not-authorised"  # a revoked seat token reaches nothing
    assert any(e["event"] == "seat-released" and e["reason"] == "no-heartbeat" for e in log(run_dir / "log.jsonl"))


async def _last_status(client, task_id, token) -> str:
    from zanni.engine.a2a_client import NotAuthorised
    try:
        return (await client.poll(task_id, token)).state
    except NotAuthorised:
        return "not-authorised"


def test_the_actor_is_done_when_released_even_if_the_director_stops_at_once(setup):
    """Recorded run 1 of milestone 3: the director exited right after the release, and the actor waited 90 s for a
    `completed` status that never came. Released means done."""
    tmp_path, actor, role, rehearsal, rehearsal_path, models = setup
    model = writer()

    async def go():
        director = rehearsal_director(rehearsal, rehearsal_path, role.manifest.name, package_hash(role.folder),
                                      tmp_path / "run", "r1", join_token="join-token-fake")
        async with serving(director, INFO) as server:
            conducting = asyncio.create_task(conduct(director, rehearsal, rehearsal_path, tmp_path / "run",
                                                     "slug-tester", lambda _: None))
            seat = asyncio.create_task(play_seat(server.url, actor, role, models, [], join_token="join-token-fake",
                                                 log_at=lambda play: tmp_path / "actor-log.jsonl", run_id="r1",
                                                 say=lambda _: None, runner=lambda t: run_cue(t, build=lambda rm: model)))
            await conducting
        return await asyncio.wait_for(seat, 10)  # the server is gone; the actor must not wait for it

    outcome = asyncio.run(go())
    assert outcome.exit_code == 0 and outcome.reason == "done"


class AwayStage:
    """A stage that answers `changes` until it goes away, then answers nothing (D47)."""

    def __init__(self, away_after: int):
        self.calls = away_after

    async def changes(self, since=None):
        return await self._maybe(([], "3"))

    async def read(self, path):
        return await self._maybe("text")

    async def _maybe(self, value):
        from zanni.actor.contract import StageError

        self.calls -= 1
        if self.calls < 0:
            raise StageError("unavailable", "the stage's server isn't answering")
        return value


def test_a_stage_that_goes_away_mid_cue_ends_the_cue_as_failed_not_as_a_crash(setup, tmp_path):
    from zanni.actor.seat import _answer
    from zanni.log import Log
    from zanni.protocol.messages import Cue

    _, _, role, _, _, models = setup
    asked = []

    def respond(messages, info):
        asked.append(len(messages))
        return ModelResponse(parts=[ToolCallPart("stage_read", {"path": "vision.md"})])

    model = FunctionModel(respond, model_name="scripted")
    cue = Cue(kind="zanni.cue", cue="c-1", scene="Specify", instructions="Read vision.md.")
    lines: list[str] = []
    report = asyncio.run(_answer(cue, AwayStage(away_after=1), role, models, [], "tester-1",
                                 Log(tmp_path / "actor.jsonl", "r1"), lines.append,
                                 lambda t: run_cue(t, build=lambda rm: model)))
    assert report.outcome == "failed" and "the stage stopped answering" in report.summary
    assert len(asked) == 1  # the model isn't asked to retry a stage that went away, and no fallback is tried
    assert report.changes == [] and report.cost is not None  # what it spent still counts, so a budget can't drop it
    assert any("failed: the stage stopped answering" in line for line in lines)

    gone = asyncio.run(_answer(cue, AwayStage(away_after=0), role, models, [], "tester-1",
                               Log(tmp_path / "actor.jsonl", "r1"), lines.append,
                               lambda t: run_cue(t, build=lambda rm: model)))
    assert gone.outcome == "failed" and "isn't answering" in gone.summary and len(asked) == 1  # no model call at all
