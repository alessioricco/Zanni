"""The stage's operations, run against the local folder and against the director's MCP server (D31)."""

import os

import pytest

from tests.stage_over_mcp import served
from zanni.actor.contract import StageError
from zanni.actor.stage import FolderStage


@pytest.fixture(params=["local", "mcp"])
def stage(request, tmp_path):
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec/a.md").write_text("AC1")
    (tmp_path / "app").mkdir()
    (tmp_path / "app/x.py").write_text("x = 1")
    local = FolderStage(tmp_path, read=["spec/"], write=["tests/"])
    if request.param == "local":
        yield local
        return
    with served({"seat-a": local}) as remote:
        yield remote["seat-a"]


def code(fn):
    with pytest.raises(StageError) as e:
        fn()
    return e.value.code


def test_read_and_write_within_permissions(stage):
    assert stage.read("spec/a.md") == "AC1"
    assert stage.write("tests/test_a.py", "ok") == "1"
    assert stage.read("tests/test_a.py") == "ok"  # writing implies reading


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "a//b", "a\\b", "", "./a"])
def test_bad_paths(stage, path):
    assert code(lambda: stage.write(path, "x")) == "invalid-path"


def test_not_permitted_names_the_rules(stage):
    with pytest.raises(StageError, match="this seat may not write app/x.py; it may write: tests/"):
        stage.write("app/x.py", "y")
    assert code(lambda: stage.read("app/x.py")) == "not-permitted"


def test_symlink_out_of_the_stage(stage, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    os.symlink(outside, stage.root / "tests")
    assert code(lambda: stage.write("tests/a.py", "x")) == "invalid-path"


def test_list_shows_only_readable_files(stage):
    stage.write("tests/t.py", "x")
    assert stage.list() == ["spec/a.md", "tests/t.py"]


def test_changes_since_a_marker(stage):
    m0 = stage.changes()[1]
    stage.write("tests/a.py", "1")
    stage.write("tests/b.py", "2")
    stage.delete("tests/a.py")
    changes, marker = stage.changes(m0)
    assert changes == [("tests/a.py", "written"), ("tests/b.py", "written"), ("tests/a.py", "deleted")]
    assert stage.changes(marker)[0] == []
    assert code(lambda: stage.changes("99")) == "unknown-marker"


def test_missing_files(stage):
    assert code(lambda: stage.read("spec/nope.md")) == "not-found"
    assert code(lambda: stage.delete("tests/nope.py")) == "not-found"
