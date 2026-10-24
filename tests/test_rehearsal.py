"""D26: a rehearsal run end to end, with a scripted model instead of a real one."""

import json
import shutil
import sys
from pathlib import Path

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from zanni.actor.rehearsal import run_rehearsal
from zanni.engine.run import run_cue
from zanni.files.check import check

EXAMPLES = Path(__file__).parents[1] / "examples"
TESTS = '''from app.slug import slugify


def test_ac1():
    assert slugify("Hello World") == "hello-world"


def test_ac2():
    assert slugify("  Zanni & Friends! ") == "zanni-friends"
'''


def setup(tmp_path, text: str | None = None) -> Path:
    shutil.copytree(EXAMPLES / "roles", tmp_path / "roles")
    # The example's verify command may download pytest; the suite runs with no network, so use this Python's pytest.
    smoke = tmp_path / "roles/slug-tester/rehearsals/smoke.yaml"
    smoke.write_text(smoke.read_text().replace("command: [uv, run, --no-project, --with, pytest, python, -m, pytest, -q, tests]",
                                               f"command: [{sys.executable}, -m, pytest, -q, tests]"))
    config = tmp_path / "slug-tester.yaml"
    config.write_text(text or (EXAMPLES / "slug-tester.yaml").read_text().replace("name: slug-tester-1",
                                                                                   f"name: t\nstate_dir: {tmp_path}/state"))
    return config


def good_writer():
    turns = [lambda: [ToolCallPart("load_skill", {"name": "write-test"}),
                      ToolCallPart("stage_read", {"path": "backlog/round-1.md"})],
             lambda: [ToolCallPart("stage_write", {"path": "tests/test_slug.py", "content": TESTS})],
             lambda: [TextPart("Wrote tests/test_slug.py: test_ac1 and test_ac2.")]]
    return FunctionModel(lambda messages, info: ModelResponse(parts=turns.pop(0)()), model_name="scripted")


def test_a_rehearsal_runs_writes_logs_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")  # never contacted: the model is scripted
    monkeypatch.setattr("zanni.actor.rehearsal.check_tool_support", lambda *a: None)
    config = setup(tmp_path)
    actor, _ = check(config)
    lines: list[str] = []
    model = good_writer()
    outcome = run_rehearsal(config, actor, say=lines.append, runner=lambda t: run_cue(t, build=lambda rm: model),
                            run_id="run1")
    assert outcome.passed, lines
    assert (outcome.run_dir / "stage/tests/test_slug.py").read_text() == TESTS
    assert not (EXAMPLES / "roles/slug-tester/rehearsals/smoke-stage/tests/test_slug.py").exists()  # package untouched
    report = outcome.reports[0]
    assert report.outcome == "done" and report.changes == ["1"] and report.cost is not None  # priced at 0 in config
    events = [json.loads(line)["event"] for line in (outcome.run_dir / "log.jsonl").read_text().splitlines()]
    assert events == ["run-started", "cue", "report", "cost", "verdict", "run-stopped"]
    assert any("verify tests-pass: passed" in line for line in lines)


def test_check_flag_validates_without_running(tmp_path):
    import subprocess
    config = setup(tmp_path)
    result = subprocess.run([sys.executable, "-m", "zanni", "--check", str(config)], capture_output=True, text=True)
    assert result.returncode == 0
    assert "play: the rehearsal 'smoke', 1 cue, run with no director" in result.stdout
    assert result.stdout.strip().endswith("Valid.")
