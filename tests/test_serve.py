"""`zanni <rehearsal> --serve`: a director serving a rehearsal to an actor anywhere (D29), on loopback here."""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.test_join import TOKEN, configuration, scripted
from zanni.actor.join import join_play
from zanni.files.check import check

EXAMPLES = Path(__file__).parents[1] / "examples"
CONFORMANCE = Path(__file__).parent / "conformance"


def zanni(*args, env_extra=None, home=None, **kwargs):
    env = {"PATH": os.environ["PATH"], "HOME": str(home or Path.cwd())} | (env_extra or {})
    return subprocess.run([sys.executable, "-m", "zanni", *map(str, args)], capture_output=True, text=True,
                          env=env, timeout=60, **kwargs)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def roles(tmp_path) -> Path:
    shutil.copytree(EXAMPLES / "roles", tmp_path / "roles")
    smoke = tmp_path / "roles/slug-tester/rehearsals/smoke.yaml"
    smoke.write_text(smoke.read_text().replace("command: [uv, run, --no-project, --with, pytest, python, -m, pytest, -q, tests]",
                                               f"command: [{sys.executable}, -m, pytest, -q, tests]"))
    return smoke


def test_an_actor_joins_a_served_rehearsal(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("ZANNI_JOIN_TOKEN", TOKEN)
    monkeypatch.setattr("zanni.actor.join.check_tool_support", lambda *a: None)
    smoke = roles(tmp_path)
    port = free_port()
    served = subprocess.Popen([sys.executable, "-m", "zanni", str(smoke), "--serve", "--listen", f"127.0.0.1:{port}"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              env={"PATH": os.environ["PATH"], "HOME": str(tmp_path), "ZANNI_JOIN_TOKEN": TOKEN})
    try:
        for _ in range(100):
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        config = configuration(tmp_path, f"http://127.0.0.1:{port}")
        actor, _ = check(config)
        outcome = join_play(config, actor, say=lambda _: None, runner=scripted())
        out, err = served.communicate(timeout=60)
    finally:
        served.kill()
    assert outcome.exit_code == 0 and outcome.reason == "done"
    assert served.returncode == 0, out + err
    assert f"Serving rehearsal 'smoke' for the role slug-tester at http://127.0.0.1:{port}" in out
    assert "Cast slug-tester-1 (slug-tester 0.1.0) as slug-tester-1" in out
    assert "verify tests-pass: passed" in out and "Rehearsal passed." in out
    assert list((tmp_path / ".zanni/rehearsals/smoke").glob("*/log.jsonl"))  # the director's log, on its machine


def test_serving_needs_a_join_token(tmp_path):
    result = zanni(roles(tmp_path), "--serve", home=tmp_path)
    assert result.returncode == 2 and "ZANNI_JOIN_TOKEN isn't set" in result.stderr


def test_serving_needs_a_role_around_the_rehearsal(tmp_path):
    result = zanni(CONFORMANCE / "valid/rehearsal-minimal.yaml", "--serve", home=tmp_path,
                   env_extra={"ZANNI_JOIN_TOKEN": TOKEN})
    assert result.returncode == 2 and "isn't in a role package's rehearsals/ folder" in result.stderr


@pytest.mark.parametrize("args,message", [
    (["--serve"], "--serve and --listen work with a rehearsal only"),
    (["--listen", "8765"], "--serve and --listen work with a rehearsal only"),
])
def test_serve_flags_on_other_files_are_refused(tmp_path, args, message):
    result = zanni(EXAMPLES / "slug-tester.yaml", *args, home=tmp_path)
    assert result.returncode == 2 and message in result.stderr


def test_a_bad_listen_address_is_refused(tmp_path):
    result = zanni(roles(tmp_path), "--serve", "--listen", "nowhere", home=tmp_path, env_extra={"ZANNI_JOIN_TOKEN": TOKEN})
    assert result.returncode == 2 and "isn't host:port" in result.stderr


def test_check_with_serve_only_validates(tmp_path):
    result = zanni(roles(tmp_path), "--serve", "--check", home=tmp_path)
    assert result.returncode == 0 and result.stdout.strip().endswith("Valid.")


def test_stopping_the_director_ends_an_open_task_stream_cleanly(tmp_path):
    """An actor may still be following its task when the director stops: the stream must end, not be cut."""
    import asyncio

    from a2a.types import SubscribeToTaskRequest

    from tests.test_director import director, join_message
    from tests.test_director import JOIN_TOKEN as DIRECTOR_TOKEN
    from zanni.director.contract import DirectorInfo
    from zanni.engine.a2a_client import DirectorClient, _context
    from zanni.engine.serve import serving

    d, _ = director(tmp_path)
    info = DirectorInfo(name="d", description="d", version="0", play="p", script="s")
    ended = {}

    async def scenario():
        async with serving(d, info) as server:
            client = DirectorClient(server.url)
            await client.fetch_card()
            task_id, cast = await client.join(join_message().card, DIRECTOR_TOKEN)

            async def follow():
                try:
                    async for _ in client._stream.subscribe(SubscribeToTaskRequest(id=task_id),
                                                            context=_context(cast.seat_token)):
                        pass
                    ended["how"] = "ended"
                except Exception as e:
                    ended["how"] = f"{type(e).__name__}: {e}"

            following = asyncio.create_task(follow())
            while not d.seats[task_id].streams:  # the director has seen the stream open
                await asyncio.sleep(0.02)
        await asyncio.wait_for(following, 10)
        await client.close()

    asyncio.run(asyncio.wait_for(scenario(), 30))
    assert ended["how"] == "ended"
