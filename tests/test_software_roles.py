"""D57: each of the software team's six roles runs its own rehearsal end to end, with a scripted model instead of a
real one. The tester and the coder work through their workspaces (D52): their files reach the stage at the cue's end."""

import shutil
import sys
from pathlib import Path

import pytest
import yaml
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from zanni.actor.rehearsal import run_rehearsal
from zanni.engine.run import run_cue
from zanni.files.check import check

EXAMPLES = Path(__file__).parents[1] / "examples"
ROLES = ["product-owner", "architect", "ui-designer", "tester", "developer-lead", "coder"]

BACKLOG = "# Round 1\n\n## Convert lengths\n- R1-1: converting 1 km to m gives 1000\n- R1-2: 12 in is 30.48 cm\n"
REVIEW = "1. R1-2 needs a tolerance: floating point. Suggest: equal to 2 decimal places.\n"
DESIGN = "# Architecture\n\n- `app/convert.py`: convert(value, from_unit, to_unit). Tests: pytest, under tests/.\n"
SCREEN = "# Converter (/)\n\nServes R1-3. A value field (id `value`), two unit lists, a Convert button.\n"
TASKS = "## convert\npaths: [app/convert.py]\ncriteria: R1-1, R1-2\n"
TESTS = "from app.convert import convert\n\n\ndef test_r1_1_km_to_m():\n    assert convert(1, 'km', 'm') == 1000\n"
CODE = ("FACTORS = {'m': 1.0, 'km': 1000.0, 'cm': 0.01, 'in': 0.0254}\n\n\n"
        "def convert(value, from_unit, to_unit):\n    return value * FACTORS[from_unit] / FACTORS[to_unit]\n")

# What each role's scripted model does in each cue: tool calls, then a reply.
WORK = {
    "product-owner": [[("load_skill", {"name": "write-backlog"}), ("stage_read", {"path": "vision.md"}),
                       ("stage_write", {"path": "backlog/round-1.md", "content": BACKLOG})]],
    "architect": [[("load_skill", {"name": "review-a-document"}),
                   ("stage_write", {"path": "reviews/round-1/backlog-architect.md", "content": REVIEW})],
                  [("load_skill", {"name": "write-architecture"}),
                   ("stage_write", {"path": "spec/architecture/overview.md", "content": DESIGN})]],
    "ui-designer": [[("stage_write", {"path": "spec/ui/converter.md", "content": SCREEN})]],
    "tester": [[("load_skill", {"name": "one-test-per-criterion"}),
                ("workspace_write_file", {"path": "tests/test_convert.py", "content": TESTS})]],
    "developer-lead": [[("load_skill", {"name": "plan-workstreams"}),
                        ("stage_write", {"path": "tasks/round-1.md", "content": TASKS})]],
    "coder": [[("load_skill", {"name": "make-the-tests-pass"}),
               ("workspace_write_file", {"path": "app/convert.py", "content": CODE})]],
}


def scripted(cues: list[list[tuple[str, dict]]]) -> FunctionModel:
    """Each cue: its tool calls in one response, then a reply once they have returned."""
    pending = [list(c) for c in cues]

    def respond(messages, info):
        last = messages[-1]
        if any(p.part_kind == "tool-return" for p in last.parts) or not pending[0]:
            pending.pop(0)
            return ModelResponse(parts=[TextPart("Done.")])
        calls, pending[0] = pending[0], []
        return ModelResponse(parts=[ToolCallPart(name, args) for name, args in calls])

    return FunctionModel(respond, model_name="scripted")


def configured(tmp_path, role: str) -> Path:
    shutil.copytree(EXAMPLES / "roles", tmp_path / "roles")
    smoke = tmp_path / f"roles/{role}/rehearsals/smoke.yaml"
    # The coder's verify command may download pytest; the suite runs with no network, so use this Python's pytest.
    smoke.write_text(smoke.read_text().replace("command: [uv, run, --no-project, --with, pytest, python, -m, pytest",
                                               f"command: [{sys.executable}, -m, pytest"))
    config = tmp_path / f"{role}.yaml"
    config.write_text(yaml.safe_dump({
        "name": f"{role}-1", "role": f"./roles/{role}", "play": f"./roles/{role}/rehearsals/smoke.yaml",
        "state_dir": str(tmp_path / "state"), "workspace": {"commands": ["pytest"]},
        "models": [{"provider": "ollama", "model": "m", "price": {"input": 0, "output": 0}}]}))
    return config


@pytest.mark.parametrize("role", ROLES)
def test_each_role_passes_its_own_rehearsal(tmp_path, monkeypatch, role):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")  # never contacted: the model is scripted
    monkeypatch.setattr("zanni.actor.join.check_tool_support", lambda *a: None)
    config = configured(tmp_path, role)
    actor, _ = check(config)
    model = scripted(WORK[role])
    lines: list[str] = []
    outcome = run_rehearsal(config, actor, say=lines.append, runner=lambda t: run_cue(t, build=lambda rm: model),
                            run_id="run1")
    assert outcome.passed, "\n".join(lines)
    assert all(r.outcome == "done" and r.changes for r in outcome.reports)
    if role in ("tester", "coder"):  # its file came through the workspace, at the end of the cue
        assert any("workspace sent to the stage: 1 written" in line for line in lines), lines
    assert not list((EXAMPLES / "roles").rglob("__pycache__"))  # the packages stay as they were


def test_the_roles_permissions_keep_each_part_to_its_own_files():
    """D57: what each part writes is a permission the stage enforces, as the vision's table says."""
    writes = {r: yaml.safe_load((EXAMPLES / f"roles/{r}/role.yaml").read_text())["needs"]["stage_write"] for r in ROLES}
    assert writes == {"product-owner": ["backlog/", "reviews/"], "architect": ["spec/architecture/", "reviews/"],
                      "ui-designer": ["spec/ui/"], "tester": ["tests/", "findings/", "reviews/"],
                      "developer-lead": ["tasks/", "reviews/"], "coder": ["app/"]}
