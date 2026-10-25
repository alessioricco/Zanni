"""D52: a seat's workspace, a local copy of the stage filled at the start of each cue and sent back at its end, and
`zanni:workspace`, the MCP server an engine works through. D54: a cue's `writes` narrow the seat's own."""

import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from tests.director_harness import actor, kata, production, until
from tests.engine.fakes import MemoryStage, scripted
from tests.test_stage_backends import BACKENDS, SEED
from zanni.actor.contract import AllModelsFailed, CueResult, CueTask, McpServerSpec, ResolvedModel
from zanni.actor.seat import _answer
from zanni.actor.workspace import Ignore, Workspace
from zanni.director.contract import DirectorInfo
from zanni.engine.run import run_cue
from zanni.engine.serve import serving
from zanni.files.schemas import ModelEntry
from zanni.log import Log
from zanni.protocol.messages import Cue
from zanni.stage.git import run_git


# The server: what an engine works through

def free() -> ResolvedModel:
    return ResolvedModel(ModelEntry(provider="ollama", model="m", price={"input": 0, "output": 0}),
                         base_url="http://localhost:11434")


def server_in(folder: Path, commands: list[str], bin_dir: Path | None = None) -> McpServerSpec:
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin" if bin_dir else "/usr/bin:/bin"}
    args = ["-m", "zanni.engine.workspace_server", "--folder", str(folder), "--timeout", "5"]
    for c in commands:
        args += ["--command", c]
    return McpServerSpec(name="workspace", command=sys.executable, args=args, env=env, cwd=str(folder))


def script_bin(tmp_path, **scripts) -> Path:
    """Small executables on a PATH of their own, standing for a project's commands."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in scripts.items():
        (bin_dir / name).write_text(f"#!/bin/sh\n{body}\n")
        (bin_dir / name).chmod(0o755)
    return bin_dir


def returns(model) -> list:
    return [p.content for m in model.seen for p in m.parts if p.part_kind in ("tool-return", "retry-prompt")]


def run_tools(server: McpServerSpec, *turns):
    model = scripted(*turns, "done")
    task = CueTask(instructions="i", skills={}, prompt="p", stage=MemoryStage(), models=[free()],
                   mcp_servers=[server])
    asyncio.run(run_cue(task, build=lambda rm: model))
    return returns(model)


def test_the_server_writes_reads_lists_and_runs_an_allowed_command(tmp_path):
    folder = tmp_path / "ws"
    folder.mkdir()
    bin_dir = script_bin(tmp_path, check='cat app/x.txt; exit 3')
    out = run_tools(server_in(folder, ["check"], bin_dir),
                    {"workspace_write_file": {"path": "app/x.txt", "content": "hello\n"}},
                    {"workspace_read_file": {"path": "app/x.txt"}},
                    {"workspace_list_files": {}},
                    {"workspace_run": {"command": ["check"]}})
    assert (folder / "app/x.txt").read_text() == "hello\n"
    assert out[1] == "hello\n" and out[2] == ["app/x.txt"]
    assert out[3] == {"exit_code": 3, "output": "hello\n"}


def test_a_command_not_listed_is_refused_and_one_past_its_timeout_is_stopped(tmp_path):
    folder = tmp_path / "ws"
    folder.mkdir()
    bin_dir = script_bin(tmp_path, slow="sleep 30", other="echo no")
    out = run_tools(server_in(folder, ["slow"], bin_dir),
                    {"workspace_run": {"command": ["other"]}},
                    {"workspace_run": {"command": ["/bin/sh", "-c", "echo no"]}},
                    {"workspace_run": {"command": ["slow"], "timeout_seconds": 1}})
    assert "not-permitted: other isn't a command this actor may run; it may run: slow" in str(out[0])
    assert "not-permitted: /bin/sh" in str(out[1])
    assert out[2]["exit_code"] is None and out[2]["output"].startswith("stopped after 1 s")


def test_a_path_that_leaves_the_workspace_is_refused(tmp_path):
    folder = tmp_path / "ws"
    folder.mkdir()
    (tmp_path / "secret.txt").write_text("outside")
    (folder / "link").symlink_to(tmp_path / "secret.txt")
    out = run_tools(server_in(folder, []),
                    {"workspace_read_file": {"path": "../secret.txt"}},
                    {"workspace_read_file": {"path": "link"}},
                    {"workspace_write_file": {"path": "/tmp/x", "content": "x"}})
    assert all("invalid-path" in str(o) for o in out)
    assert (tmp_path / "secret.txt").read_text() == "outside"


# The workspace: filled from the stage, sent back through the permission layer, on every backend

@pytest.fixture(params=sorted(BACKENDS))
def backend(request):
    return BACKENDS[request.param]


def on(backend, tmp_path, body):
    async def go():
        async with backend(tmp_path) as stage:
            return await body(stage)
    return asyncio.run(go())


def test_fill_copies_what_the_seat_may_read_and_sync_sends_back_what_changed(backend, tmp_path):
    ws = Workspace(tmp_path / "ws")

    async def body(stage):
        seat = stage.seat(read=["app/"], write=["app/"], who="coder-1")
        seat.start_cue("r1-c1: Build", ["app/"])
        await ws.fill(seat)
        copied = sorted(p.relative_to(ws.folder).as_posix() for p in ws.folder.rglob("*") if p.is_file())
        (ws.folder / "app/x.py").write_text("x = 2\n")
        (ws.folder / "app/y.py").write_text("y = 1\n")
        synced = await ws.sync(seat)
        return copied, synced, await seat.read("app/x.py"), await seat.read("app/y.py"), seat.end_cue(), stage

    copied, synced, x, y, refused, stage = on(backend, tmp_path, body)
    assert copied == ["app/x.py"]  # spec/a.md is on the stage, but this seat may not read it
    assert (synced.written, synced.deleted, synced.refused, refused) == (["app/x.py", "app/y.py"], [], [], [])
    assert (x, y) == ("x = 2\n", "y = 1\n")
    if backend is BACKENDS["git"]:
        authors = run_git("log", "--format=%an %s", "-2", cwd=tmp_path / "clone").stdout.splitlines()
        assert authors == ["coder-1 r1-c1: Build", "coder-1 r1-c1: Build"]


def test_a_change_outside_the_cues_paths_is_refused_listed_and_the_stage_unchanged(backend, tmp_path):
    ws = Workspace(tmp_path / "ws")

    async def body(stage):
        seat = stage.seat(read=["app/", "spec/"], write=["app/"], who="coder-1")
        seat.start_cue("r1-c2: Fix", ["app/y.py"])  # the cue names one file; the seat may write all of app/
        await ws.fill(seat)
        (ws.folder / "app/x.py").write_text("x = 3\n")  # another workstream's file
        (ws.folder / "spec/a.md").unlink()  # and a file this seat may never write
        (ws.folder / "app/y.py").write_text("y = 2\n")
        synced = await ws.sync(seat)
        return synced, seat.end_cue(), await seat.read("app/x.py"), await seat.read("spec/a.md")

    synced, refused, x, spec = on(backend, tmp_path, body)
    assert synced.written == ["app/y.py"] and synced.deleted == []
    assert [r.split(":")[0] for r in synced.refused] == ["write app/x.py", "delete spec/a.md"]
    assert refused == ["write app/x.py", "delete spec/a.md"]  # the director's own record, for the report
    assert (x, spec) == (SEED["app/x.py"], SEED["spec/a.md"])


def test_ignored_and_binary_files_never_reach_the_stage(tmp_path):
    ws = Workspace(tmp_path / "ws")

    async def body(stage):
        seat = stage.seat(read=["/"], write=["/"], who="coder-1")
        await ws.fill(seat)
        (ws.folder / ".gitignore").write_text("__pycache__/\n*.log\n!keep.log\n/build\n")
        for path, text in {"app/__pycache__/x.txt": "c", "app/run.log": "l", "app/keep.log": "k", "build/out": "o",
                           "app/build/kept": "b"}.items():
            (ws.folder / path).parent.mkdir(parents=True, exist_ok=True)
            (ws.folder / path).write_text(text)
        (ws.folder / "app/blob.bin").write_bytes(b"\xff\xfe\x00")
        return await ws.sync(seat)

    synced = on(BACKENDS["folder"], tmp_path, body)
    assert synced.written == [".gitignore", "app/build/kept", "app/keep.log"]


def test_gitignore_patterns_as_git_reads_them():
    ignore = Ignore("# build output\nnode_modules/\n*.pyc\n!keep.pyc\n/dist\ndocs/**/draft.md\n")
    assert ignore.ignores("node_modules/a/b.js") and ignore.ignores("web/node_modules/x.js")
    assert ignore.ignores("app/x.pyc") and not ignore.ignores("app/keep.pyc")
    assert ignore.ignores("dist/a.js") and not ignore.ignores("app/dist/a.js")
    assert ignore.ignores("docs/a/b/draft.md") and ignore.ignores("docs/draft.md")
    assert not ignore.ignores("app/node_modules.py")


# A seat's cue: the workspace is filled before, and sent back only when the cue ends done

def cue() -> Cue:
    return Cue(kind="zanni.cue", cue="r1-c1", scene="Build", instructions="Write app/y.py.", writes=["app/"])


def answer(tmp_path, runner):
    ws = Workspace(tmp_path / "ws")

    class Role:  # what _answer reads of a role
        instructions, skills = "i", {}
        manifest = type("M", (), {"model": type("N", (), {"needs": type("T", (), {"tools": False})})})

    async def go():
        async with BACKENDS["folder"](tmp_path) as stage:
            seat = stage.seat(read=["app/"], write=["app/"], who="coder-1")
            report = await _answer(cue(), seat, Role, [free()], [], "coder-1", Log(tmp_path / "actor.jsonl", "r1"),
                                   lambda _: None, runner, ws)
            return report, await seat.list("app/")
    return ws, asyncio.run(go())


def result() -> CueResult:
    return CueResult(output="Done.", model="ollama m", provider="ollama", model_name="m", tool_calls=[],
                     input_tokens=1, output_tokens=1, requests=1, cost=Decimal(0), cost_source="configuration")


def test_a_finished_cue_sends_its_workspace_and_a_failed_one_sends_nothing(tmp_path):
    def engine(fails: bool):
        async def runner(task):
            (tmp_path / ("ok" if not fails else "ko") / "ws/app/y.py").write_text("y = 1\n")  # the engine's edit
            if fails:
                raise AllModelsFailed([])
            return result()
        return runner

    (tmp_path / "ok").mkdir()
    _, (report, files) = answer(tmp_path / "ok", engine(fails=False))
    assert report.outcome == "done" and files == ["app/x.py", "app/y.py"]
    (tmp_path / "ko").mkdir()
    _, (report, files) = answer(tmp_path / "ko", engine(fails=True))
    assert report.outcome == "failed" and files == ["app/x.py"]  # half-done work never reaches the stage


# End to end: an actor with a workspace, over the director's stage server on loopback

def test_a_cues_workspace_reaches_the_stage_over_mcp_and_the_report_lists_what_was_refused(tmp_path):
    play, script, stage_folder = kata(tmp_path, gates=())
    p = production(tmp_path, play, script, stage_folder)
    ws = Workspace(tmp_path / "coder-ws")

    async def runner(task):  # stands for an engine working in the folder
        (ws.folder / "app/slug.py").write_text("def slug(s): return s\n")
        (ws.folder / "tests/test_extra.py").write_text("# not the coder's to write\n")
        return result()

    async def go():
        info = DirectorInfo(name="d", description="t", version="0", play="kata", script="./kata")
        async with serving(p.casting, info) as server:
            task = asyncio.create_task(actor(server.url, tmp_path, "coder", runner, workspace=ws))
            await until(lambda: p.active_seats("coder"))
            await p.cue("coder", "Build", "Write app/slug.py.", writes=["app/"])
            text = await p.wait_for_reports()
            await p.finish()
            await task
            return text

    text = asyncio.run(go())
    assert (stage_folder / "app/slug.py").read_text() == "def slug(s): return s\n"
    assert not (stage_folder / "tests/test_extra.py").exists()
    assert 'refused="write tests/test_extra.py"' in text and 'outcome="done"' in text
    reports = [json.loads(line) for line in (tmp_path / "log.jsonl").read_text().splitlines()
               if '"event": "report"' in line]
    assert reports[-1]["refused"] == ["write tests/test_extra.py"] and len(reports[-1]["changes"]) == 1
