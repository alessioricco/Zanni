"""D55: a script's check files, run by its verifiers from a folder beside the snapshot, never from the stage; and the
software script's three checks, which work for any stack: criteria named by tests, tests that fail, an app that
starts."""

import asyncio
import socket
import subprocess
import sys
from pathlib import Path

from tests.director_harness import EXAMPLES, kata, production
from zanni.actor.verifier import run_verify
from zanni.files.check import verifier_commands
from zanni.files.hashing import package_hash
from zanni.files.schemas import Script
from zanni.log import Log
from zanni.protocol.messages import Verify
from zanni.stage import folder_stage

CHECKS = EXAMPLES / "scripts/software-team/checks"


def check(name: str, *args, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CHECKS / name), *map(str, args)], capture_output=True, text=True,
                          cwd=cwd, timeout=60)


def files(root: Path, tree: dict[str, str]) -> Path:
    for path, text in tree.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    return root


# criteria.py

def test_every_criterion_of_the_latest_round_named_by_a_test_passes(tmp_path):
    files(tmp_path, {"backlog/round-1.md": "- R1-1 old\n", "backlog/round-2.md": "- R2-1 converts\n- R2-2 rejects\n",
                     "tests/test_convert.py": "def test_r2_1_converts(): ...\n",
                     "tests/convert.test.js": "test('R2-2 rejects bad units', () => {})\n"})
    result = check("criteria.py", tmp_path / "backlog", tmp_path / "tests")
    assert result.returncode == 0, result.stdout
    assert "every one of the 2 criteria" in result.stdout


def test_a_criterion_no_test_names_fails_and_says_which(tmp_path):
    files(tmp_path, {"backlog/round-1.md": "- R1-1 a\n- R1-2 b\n- R1-12 c\n", "tests/t.py": "# R1-1 and R1-12\n"})
    result = check("criteria.py", tmp_path / "backlog", tmp_path / "tests")
    assert result.returncode == 1 and "1 of 3 criteria" in result.stdout and "R1-2" in result.stdout


def test_a_backlog_without_ids_or_without_a_round_fails(tmp_path):
    files(tmp_path, {"backlog/notes.md": "x\n"})
    assert "no backlog file" in check("criteria.py", tmp_path / "backlog", tmp_path / "tests").stdout
    files(tmp_path, {"backlog/round-1.md": "- converts units\n"})
    assert "names no criterion id" in check("criteria.py", tmp_path / "backlog", tmp_path / "tests").stdout


# expect_failure.py

def exits(code: int) -> list[str]:
    return [sys.executable, "-c", f"import sys; print('ran'); sys.exit({code})"]


def test_tests_that_fail_pass_the_check_and_tests_that_pass_or_break_fail_it():
    assert check("expect_failure.py", "--", *exits(1)).returncode == 0
    assert check("expect_failure.py", "--", *exits(0)).returncode == 1
    assert check("expect_failure.py", "--", *exits(2)).returncode == 1  # a broken runner isn't a failing test
    assert check("expect_failure.py", "--code", 3, "--", *exits(3)).returncode == 0


# app_starts.py

def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


SERVE = ("import http.server, os; http.server.ThreadingHTTPServer(('127.0.0.1', int(os.environ['PORT'])), "
         "http.server.SimpleHTTPRequestHandler).serve_forever()")


def test_an_app_that_answers_on_its_port_passes_and_is_stopped(tmp_path):
    port = free_port()
    result = check("app_starts.py", "--port", port, "--", sys.executable, "-c", SERVE, cwd=tmp_path)
    assert result.returncode == 0, result.stdout
    assert f"answered at http://127.0.0.1:{port}/ with HTTP 200" in result.stdout
    with socket.socket() as s:  # stopped: nothing listens there any more
        assert s.connect_ex(("127.0.0.1", port)) != 0


def test_an_app_that_exits_or_never_answers_fails():
    port = free_port()
    assert "exited with code 4" in check("app_starts.py", "--port", port, "--", *exits(4)).stdout
    slow = [sys.executable, "-c", "import time; time.sleep(30)"]
    assert check("app_starts.py", "--port", port, "--wait", 1, "--", *slow).returncode == 1


# Running them: beside the snapshot, never on the stage

def with_check_files(tmp_path):
    play, script, stage = kata(tmp_path, gates=())
    folder = tmp_path / "script"
    files(folder, {"checks/count.py": "import sys\nfrom pathlib import Path\n"
                                      "sys.exit(0 if len(list(Path('tests').glob('*.py'))) >= 1 else 1)\n"})
    script = Script.model_validate({**script.model_dump(), "verifiers": {"has-tests": {
        "description": "the stage has tests", "files": ["checks/count.py"],
        "command": [sys.executable, "${ZANNI_SCRIPT}/checks/count.py"]}}, "stop": {}})
    return play, script, stage, folder


def test_the_director_runs_a_check_file_beside_the_snapshot_and_never_puts_it_on_the_stage(tmp_path):
    play, script, stage, folder = with_check_files(tmp_path)
    p = production(tmp_path, play, script, stage)
    p.verifiers = verifier_commands(play, script, folder)
    assert p.verifiers["has-tests"].files == {"checks/count.py": (folder / "checks/count.py").read_text()}
    assert "has-tests: failed" in asyncio.run(p.run_verifier("has-tests"))  # the stage has no tests yet
    (stage / "tests/test_slug.py").write_text("def test_slug(): ...\n")
    assert "has-tests: passed" in asyncio.run(p.run_verifier("has-tests"))
    assert not (stage / "checks").exists() and not list(stage.rglob("count.py"))


def test_a_verifier_seat_receives_the_check_files_with_the_command(tmp_path):
    stage = files(tmp_path / "stage", {"tests/test_a.py": "def test_a(): ...\n"})
    verify = Verify(kind="zanni.verify", verify="v1", verifier="has-tests", timeout="30", marker="0",
                    command=[sys.executable, "${ZANNI_SCRIPT}/checks/count.py"],
                    files={"checks/count.py": "import sys\nfrom pathlib import Path\n"
                                              "sys.exit(0 if list(Path('tests').glob('*.py')) else 1)\n"})

    async def go():
        seat = folder_stage(stage).seat(read=["/"], write=[], who="checker")
        return await run_verify(verify, seat, "checker", Log(tmp_path / "seat.jsonl", "r1"), lambda _: None)

    verdict = asyncio.run(go())
    assert verdict.passed and verdict.exit_code == "0"
    assert sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()) == ["tests/test_a.py"]


def test_a_check_file_is_part_of_the_scripts_pinned_hash(tmp_path):
    """play.lock pins a package by its content hash (D37), so a check file changed after locking doesn't match."""
    folder = files(tmp_path / "script", {"SCRIPT.md": "x", "checks/criteria.py": "print(1)\n"})
    before = package_hash(folder)
    (folder / "checks/criteria.py").write_text("print(2)\n")
    assert package_hash(folder) != before
