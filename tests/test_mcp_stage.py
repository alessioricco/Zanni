"""A play on an `mcp` stage (D47): the example SQLite stage server as the stage, reached with the director's token;
a wrong token starts nothing; a server that goes away pauses the play until it's back and the owner resumes it; a
server that doesn't take `author` and `note` still works; the token is in no log."""

import asyncio
import json
import os
import socket
import sqlite3
import subprocess
import sys

import yaml

from tests.director_harness import Steps, kata, production, run_turn, until
from tests.fake_openai import fake_openai
from tests.test_play_command import DIRECTOR_DONE, PY, env, play_folder, wait_until, zanni
from tests.test_stage_backends import EXAMPLE_SERVER, STAGE_TOKEN, sqlite_stage_server
from zanni.engine.stage_backend import McpBackend
from zanni.stage import Stage, StageError


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(tmp_path, seed, port, token=STAGE_TOKEN):
    """The example server as its own process, as a user would run it."""
    proc = subprocess.Popen([sys.executable, "-B", str(EXAMPLE_SERVER), "--db", str(tmp_path / "stage.db"),
                             "--listen", f"127.0.0.1:{port}", "--seed", str(seed)], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, env={**os.environ, "ZANNI_STAGE_TOKEN": token})
    def up():
        with socket.socket() as s:
            return s.connect_ex(("127.0.0.1", port)) == 0
    wait_until(up, 30)
    return proc


def on_mcp(folder, port):
    play = yaml.safe_load((folder / "play.yaml").read_text())
    play["stage"] = {"backend": "mcp", "url": f"http://127.0.0.1:{port}/mcp"}
    (folder / "play.yaml").write_text(yaml.safe_dump(play))
    director = yaml.safe_load((folder / "director.yaml").read_text())
    director["credentials"]["ZANNI_STAGE_TOKEN"] = "${ZANNI_STAGE_TOKEN}"
    (folder / "director.yaml").write_text(yaml.safe_dump(director))


def test_a_play_runs_on_the_example_sqlite_stage_server(tmp_path):
    port = free_port()
    with fake_openai() as (url, _, scripts):
        scripts["director"] = list(DIRECTOR_DONE)
        folder = play_folder(tmp_path, url)
        server = start_server(tmp_path, folder / "stage", port)
        try:
            on_mcp(folder, port)
            proc = subprocess.Popen([PY, "-m", "zanni", str(folder / "play.yaml")], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL,
                                    env=env(tmp_path, ZANNI_STAGE_TOKEN=STAGE_TOKEN))
            try:
                wait_until(lambda: "waiting at a gate" in zanni("gate", folder / "play.yaml", tmp_path=tmp_path).stdout,
                           90)
                zanni("gate", folder / "play.yaml", "approve", tmp_path=tmp_path)
                out, err = proc.communicate(timeout=120)
            finally:
                proc.kill()
        finally:
            server.kill()
    assert proc.returncode == 0, out + err
    db = sqlite3.connect(tmp_path / "stage.db")
    rows = dict(db.execute("select path, author from files where path in ('app/slug.py', 'tests/test_slug.py')"))
    assert rows == {"app/slug.py": "coder-1", "tests/test_slug.py": "tester-1"}  # who wrote what, on the server
    assert not (folder / "stage/app/slug.py").exists()  # the play's folder isn't the stage: the server is
    log_text = next((folder / "log").glob("*.jsonl")).read_text()
    assert STAGE_TOKEN not in log_text and STAGE_TOKEN not in out + err


def test_a_wrong_token_starts_nothing(tmp_path):
    port = free_port()
    with fake_openai() as (url, calls, _):
        folder = play_folder(tmp_path, url)
        server = start_server(tmp_path, folder / "stage", port)
        try:
            on_mcp(folder, port)
            result = zanni(folder / "play.yaml", tmp_path=tmp_path, ZANNI_STAGE_TOKEN="not-the-token")
        finally:
            server.kill()
        assert calls == []
    assert result.returncode == 2 and "couldn't reach the stage's server" in result.stderr
    assert "the server refused the token (HTTP 401)" in result.stderr
    assert "not-the-token" not in result.stderr + result.stdout


def test_the_play_pauses_when_the_server_goes_away_and_resumes_when_its_back(tmp_path):
    play, script, stage_folder = kata(tmp_path, gates=())
    seed = {p.relative_to(stage_folder).as_posix(): p.read_text() for p in stage_folder.rglob("*") if p.is_file()}
    port = free_port()

    async def go():
        async with sqlite_stage_server(tmp_path, seed, port=port) as (url, _):
            backend = McpBackend(url, STAGE_TOKEN, retries=(0.1, 0.1))
            await backend.open()
        p = production(tmp_path, play, script, stage_folder)
        p.stage = p.casting.stage = Stage(backend)
        p.view = p.stage.seat(["/"], [])
        # the turn ends right after the read that found the server gone: no model request follows it
        steps = Steps([[("read", {"path": "backlog/round-1.md"})],
                       [("read", {"path": "backlog/round-1.md"})], [("stop", {"reason": "checked"})], "ok"])

        async def owner():
            await until(lambda: p.state.paused is not None, 30)
            async with sqlite_stage_server(tmp_path, {}, port=port):  # back, on the same port and database
                assert p.gates.decide("resume", "the server is back") is None
                await until(lambda: p.state.stopped is not None, 30)

        decided = asyncio.create_task(owner())
        result = await p.direct(run_turn(p, steps))
        await decided
        await backend.close()
        return result, [s for s in steps.seen if not s.startswith("prompt: ")], p

    (reason, completed), seen, p = asyncio.run(go())
    assert (reason, completed) == ("checked", False)
    # the read that found the server gone ended turn 1 at once; turn 2, after the resume, reads it
    assert seen[0].startswith("read: # Round 1") and not any("unavailable" in s for s in seen)
    assert p.state.turns == 2
    events = [json.loads(line)["event"] for line in (tmp_path / "log.jsonl").read_text().splitlines()]
    assert events.index("stage-unavailable") < events.index("paused") < events.index("resumed")


def test_a_server_that_doesnt_take_author_and_note_still_works(tmp_path):
    from mcp.server.mcpserver import MCPServer

    from tests.test_stage_backends import sqlite_server_module
    from zanni.engine.a2a_server import listening

    module = sqlite_server_module()
    store = module.Store(tmp_path / "plain.db")
    server = MCPServer("plain", token_verifier=module.OneToken(STAGE_TOKEN),
                       auth=module.AuthSettings(issuer_url="http://127.0.0.1", resource_server_url=None))

    @server.tool()
    def stage_write(path: str, content: str) -> str:
        return store.write(path, content, None, None)

    @server.tool()
    def stage_read(path: str) -> str:
        return store.read(path)

    @server.tool()
    def stage_changes(since: str | None = None) -> dict:
        return store.changes(since)

    app = server.streamable_http_app(stateless_http=True, json_response=True, host="127.0.0.1")

    async def go():
        async with listening(lambda u: app) as s:
            backend = McpBackend(f"{s.url}/mcp", STAGE_TOKEN)
            await backend.open()
            stage = Stage(backend)
            marker = await stage.seat(["/"], ["/"], "writer-1").write("notes.md", "hello\n")
            text = await stage.seat(["/"], []).read("notes.md")
            await stage.close()
            return marker, text

    assert asyncio.run(go()) == ("1", "hello\n")  # the SDK ignores the arguments a tool doesn't declare


def test_a_stage_server_that_was_never_up_fails_in_plain_words():
    async def go():
        backend = McpBackend(f"http://127.0.0.1:{free_port()}/mcp", STAGE_TOKEN, retries=())
        try:
            await backend.open()
        except StageError as e:
            return e.code
    assert asyncio.run(go()) == "unavailable"


def test_a_strict_server_that_rejects_author_and_note_gets_writes_without_them():
    class Strict:
        def __init__(self):
            self.calls = []

        async def _call(self, tool, **args):
            self.calls.append((tool, sorted(args)))
            if "author" in args:
                raise StageError("invalid-path", "Unexpected keyword argument 'author'")
            return "1"

    backend = McpBackend("http://127.0.0.1:9/mcp", STAGE_TOKEN)
    backend._remote = Strict()
    assert asyncio.run(backend.write("a.md", "x", author="w-1", note="c1")) == "1"
    assert asyncio.run(backend.write("b.md", "y", author="w-1", note="c2")) == "1"
    assert backend.labels is False and backend._remote.calls == [
        ("stage_write", ["author", "content", "note", "path"]), ("stage_write", ["content", "path"]),
        ("stage_write", ["content", "path"])]


def test_the_directors_turn_ends_once_a_seats_call_finds_the_server_down(tmp_path):
    play, script, stage_folder = kata(tmp_path, gates=())
    p = production(tmp_path, play, script, stage_folder)
    p.stage.backend.down = None
    assert not p.turn_should_end()
    p.stage.backend.down = "the stage's server at http://127.0.0.1:9/mcp isn't answering"  # set by any seat's call
    assert p.turn_should_end()  # so the play pauses before the model's next request, not after a long wait
