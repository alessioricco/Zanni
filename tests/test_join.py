"""`zanni <actor configuration>` joining a director at a URL or through a play file (D30), on loopback."""

import asyncio
import contextlib
import json
import shutil
import threading
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from zanni.actor.join import join_play
from zanni.actor.resolve import Unresolved
from zanni.actor.roles import load_role
from zanni.actor.seat import CannotJoin
from zanni.director.contract import DirectorInfo
from zanni.director.rehearsal import conduct, rehearsal_director
from zanni.engine.run import run_cue
from zanni.engine.serve import serving
from zanni.files.check import check, load_rehearsal
from zanni.files.hashing import package_hash

EXAMPLES = Path(__file__).parents[1] / "examples"
TOKEN = "join-token-fake"


@contextlib.contextmanager
def director(tmp_path):
    """Serve the slug-tester smoke rehearsal on loopback, on a background event loop, like `--serve` would."""
    shutil.copytree(EXAMPLES / "roles", tmp_path / "roles")
    path = tmp_path / "roles/slug-tester/rehearsals/smoke.yaml"
    _, rehearsal = load_rehearsal(path)
    role = load_role(tmp_path / "roles/slug-tester")
    d = rehearsal_director(rehearsal, path, "slug-tester", package_hash(role.folder), tmp_path / "served", "r1",
                           join_token=TOKEN)
    info = DirectorInfo(name="d", description="served", version="0", play="rehearsal:smoke", script=str(path))
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    ready = loop.create_future()

    async def main():
        async with serving(d, info) as server:
            ready.set_result(server.url)
            return await conduct(d, rehearsal, path, tmp_path / "served", "slug-tester", lambda _: None)

    done = asyncio.run_coroutine_threadsafe(main(), loop)
    url = asyncio.run_coroutine_threadsafe(asyncio.wait_for(asyncio.shield(ready), 20), loop).result(20)
    try:
        yield url, done
    finally:
        if not done.done():
            loop.call_soon_threadsafe(lambda: [t.cancel() for t in asyncio.all_tasks(loop)])
        loop.call_soon_threadsafe(loop.stop)


def configuration(tmp_path, play: str, *, token: bool = True) -> Path:
    config = tmp_path / "actor.yaml"
    text = (EXAMPLES / "slug-tester.yaml").read_text()
    text = text.replace("play: ./roles/slug-tester/rehearsals/smoke.yaml", f"play: {play}")
    text = text.replace("name: slug-tester-1", f"name: slug-tester-1\nstate_dir: {tmp_path}/state")
    if token:
        text = text.replace("credentials:\n", "credentials:\n  ZANNI_JOIN_TOKEN: ${ZANNI_JOIN_TOKEN}\n")
    config.write_text(text)
    return config


def scripted():
    turns = [lambda: [ToolCallPart("stage_write", {"path": "tests/test_slug.py", "content": "def test(): pass\n"})],
             lambda: [TextPart("Done.")]]
    model = FunctionModel(lambda m, i: ModelResponse(parts=turns.pop(0)()), model_name="scripted")
    return lambda task: run_cue(task, build=lambda rm: model)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("ZANNI_JOIN_TOKEN", TOKEN)
    monkeypatch.setattr("zanni.actor.join.check_tool_support", lambda *a: None)


@pytest.mark.parametrize("through", ["url", "play-file"])
def test_an_actor_configuration_joins_a_director(tmp_path, through):
    with director(tmp_path) as (url, done):
        play = url
        if through == "play-file":
            (tmp_path / "play.yaml").write_text(f"name: x\nscript: ./s\ndirector: {url}\nstage: ./st\ncast:\n  a: roles/a\n")
            play = "./play.yaml"
        config = configuration(tmp_path, play)
        actor, _ = check(config)
        lines: list[str] = []
        outcome = join_play(config, actor, say=lines.append, runner=scripted())
        assert outcome.exit_code == 0 and outcome.reason == "done", lines
        assert done.result(20).reports[0].outcome == "done"
    assert any(line.startswith("Joining the play 'rehearsal:smoke'") for line in lines)
    logs = list((tmp_path / "state/plays/rehearsal-smoke").glob("*/log.jsonl"))
    assert len(logs) == 1  # the actor's own log, on its own machine (D32)
    assert [json.loads(line)["event"] for line in logs[0].read_text().splitlines()][0] == "joined"


def test_joining_needs_the_join_token_in_credentials_or_the_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("ZANNI_JOIN_TOKEN")
    with director(tmp_path) as (url, _):
        config = configuration(tmp_path, url, token=False)
        actor, _ = check(config)
        with pytest.raises(Unresolved, match="ZANNI_JOIN_TOKEN isn't in the actor configuration's `credentials` or "
                                             "the environment"):
            join_play(config, actor)


def test_the_join_token_may_come_from_the_environment_alone(tmp_path):
    with director(tmp_path) as (url, done):
        config = configuration(tmp_path, url, token=False)
        actor, _ = check(config)
        outcome = join_play(config, actor, say=lambda _: None, runner=scripted())
    assert outcome.exit_code == 0 and outcome.reason == "done"


def test_a_play_file_without_a_director_is_joined_through_its_director_only(tmp_path):
    shutil.copytree(EXAMPLES / "roles", tmp_path / "roles")
    (tmp_path / "play.yaml").write_text("name: x\nscript: ./s\nstage: ./st\ncast:\n  a: roles/a\n")
    config = configuration(tmp_path, "./play.yaml")
    actor, _ = check(config)
    with pytest.raises(CannotJoin, match="it runs on its director's machine"):
        join_play(config, actor)


def test_nothing_listening_is_a_plain_error(tmp_path):
    shutil.copytree(EXAMPLES / "roles", tmp_path / "roles")
    config = configuration(tmp_path, "http://127.0.0.1:9")
    actor, _ = check(config)
    with pytest.raises(CannotJoin, match="couldn't fetch the director's card"):
        join_play(config, actor)


def test_the_command_exits_2_when_it_cant_join(tmp_path):
    import subprocess
    import sys
    shutil.copytree(EXAMPLES / "roles", tmp_path / "roles")
    config = configuration(tmp_path, "http://127.0.0.1:9")
    result = subprocess.run([sys.executable, "-m", "zanni", str(config)], capture_output=True, text=True, timeout=60,
                            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "OLLAMA_BASE_URL": "http://127.0.0.1:9",
                                 "ZANNI_JOIN_TOKEN": TOKEN})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "couldn't join: couldn't fetch the director's card" in result.stderr
