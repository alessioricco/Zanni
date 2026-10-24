"""What every stage backend must pass (D43): the same operations, permissions, markers and errors, whatever stores
the stage. Each backend is added to BACKENDS: folder here, git (item 4) and mcp (item 5) beside it."""

import asyncio
import contextlib

import pytest

from zanni.stage import Stage, StageError, folder_stage

SEED = {"spec/a.md": "AC1\n", "app/x.py": "x = 1\n"}


@contextlib.asynccontextmanager
async def folder(tmp_path):
    root = tmp_path / "stage"
    for path, text in SEED.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    stage = folder_stage(root)
    try:
        yield stage
    finally:
        await stage.close()


BACKENDS = {"folder": folder}


@pytest.fixture(params=sorted(BACKENDS))
def backend(request):
    return BACKENDS[request.param]


def play(backend, tmp_path, body):
    """Run `body(stage)` on a fresh stage of this backend, seeded with SEED."""
    async def go():
        async with backend(tmp_path) as stage:
            return await body(stage)
    return asyncio.run(go())


async def code(coro) -> str:
    with pytest.raises(StageError) as e:
        await coro
    return e.value.code


def test_read_write_list_delete_within_permissions(backend, tmp_path):
    async def body(stage: Stage):
        tester = stage.seat(["spec/"], ["tests/"], "tester-1")
        assert await tester.read("spec/a.md") == "AC1\n"
        assert await tester.write("tests/test_a.py", "ok\n") == "1"
        assert await tester.read("tests/test_a.py") == "ok\n"  # writing implies reading
        assert await tester.list() == ["spec/a.md", "tests/test_a.py"]  # app/ isn't readable to it
        assert await tester.list("tests") == ["tests/test_a.py"]
        assert await tester.delete("tests/test_a.py") == "2"
        assert await code(tester.read("tests/test_a.py")) == "not-found"
    play(backend, tmp_path, body)


def test_a_seat_writing_outside_its_permissions_changes_nothing(backend, tmp_path):
    async def body(stage: Stage):
        tester = stage.seat(["spec/"], ["tests/"], "tester-1")
        assert await code(tester.write("app/x.py", "y = 2\n")) == "not-permitted"
        assert await code(tester.delete("app/x.py")) == "not-permitted"
        assert await code(tester.read("app/x.py")) == "not-permitted"
        director = stage.seat(["/"], [])
        assert await director.read("app/x.py") == "x = 1\n" and stage.marker() == 0
    play(backend, tmp_path, body)


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "a//b", "a\\b", "", "./a"])
def test_bad_paths_are_refused_before_the_backend(backend, tmp_path, path):
    async def body(stage: Stage):
        return await code(stage.seat(["/"], ["/"], "s").write(path, "x"))
    assert play(backend, tmp_path, body) == "invalid-path"


def test_markers_and_changes_are_the_records_on_every_backend(backend, tmp_path):
    async def body(stage: Stage):
        a, b = stage.seat(["/"], ["tests/"], "a"), stage.seat(["/"], ["app/"], "b")
        m0 = (await a.changes())[1]
        await a.write("tests/t.py", "1")
        await b.write("app/x.py", "2")
        await a.delete("tests/t.py")
        changes, marker = await a.changes(m0)
        assert changes == [("tests/t.py", "written"), ("app/x.py", "written"), ("tests/t.py", "deleted")]
        assert marker == "3" and (await a.changes(marker))[0] == []
        assert await code(a.changes("99")) == "unknown-marker"
        assert stage.made_by("a", 0) == ["1", "3"] and stage.made_by("b", 0) == ["2"]
        assert all(c.backend_marker for c in stage.record)  # the backend's own marker, kept beside each change
    play(backend, tmp_path, body)


def test_the_last_write_wins_and_the_record_says_who(backend, tmp_path):
    async def body(stage: Stage):
        a, b = stage.seat(["/"], ["/"], "a"), stage.seat(["/"], ["/"], "b")
        await asyncio.gather(a.write("notes.md", "from a\n"), b.write("notes.md", "from b\n"))
        last = stage.record[-1].seat
        assert await a.read("notes.md") == f"from {last}\n"
        assert {c.seat for c in stage.record} == {"a", "b"}
    play(backend, tmp_path, body)


def test_a_snapshot_is_the_stage_as_a_folder_and_changes_nothing(backend, tmp_path):
    async def body(stage: Stage):
        coder = stage.seat(["/"], ["app/"], "coder-1")
        await coder.write("app/y.py", "y = 2\n")
        into = tmp_path / "snap"
        into.mkdir()
        marker = await stage.snapshot(into)
        assert marker == stage.marker() == 1
        assert (into / "spec/a.md").read_text() == "AC1\n" and (into / "app/y.py").read_text() == "y = 2\n"
        (into / "app/y.py").write_text("changed in the snapshot\n")
        assert await coder.read("app/y.py") == "y = 2\n"
    play(backend, tmp_path, body)


def test_missing_expects_names_files_and_folders(backend, tmp_path):
    async def body(stage: Stage):
        return await stage.missing(["spec/a.md", "spec/", "vision.md", "backlog/"])
    assert play(backend, tmp_path, body) == ["vision.md", "backlog/"]
