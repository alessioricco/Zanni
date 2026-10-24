"""The slug kata (D40): the slug-coder's rehearsal, and the whole example play run end to end, from a copy of
examples/, with the director and the local seats scripted on a fake OpenAI-compatible server."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from tests.fake_openai import fake_openai
from zanni.actor.rehearsal import run_rehearsal
from zanni.engine.run import run_cue
from zanni.files.check import check

EXAMPLES = Path(__file__).parents[1] / "examples"
PY = sys.executable
SLUG = 'import re\n\n\ndef slugify(text, max_length=None):\n    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")\n'
TESTS = ('from app.slug import slugify\n\n\ndef test_ac1():\n    assert slugify("Hello World") == "hello-world"\n\n\n'
         'def test_ac2():\n    assert slugify("  Zanni & Friends! ") == "zanni-friends"\n')
UV_PYTEST = "[uv, run, --no-project, --with, pytest, python, -m, pytest, -q, tests]"


def test_the_slug_coders_rehearsal_passes_with_a_scripted_model(tmp_path, monkeypatch):
    monkeypatch.setattr("zanni.actor.join.check_tool_support", lambda *a: None)
    shutil.copytree(EXAMPLES / "roles", tmp_path / "roles")
    smoke = tmp_path / "roles/slug-coder/rehearsals/smoke.yaml"
    smoke.write_text(smoke.read_text().replace(f"command: {UV_PYTEST}", f"command: [{PY}, -m, pytest, -q, tests]"))
    config = tmp_path / "coder.yaml"
    config.write_text(yaml.safe_dump({"name": "c", "role": "./roles/slug-coder", "play": str(smoke),
                                      "state_dir": str(tmp_path / "state"),
                                      "models": [{"provider": "openai-compatible", "model": "m",
                                                  "base_url": "http://127.0.0.1:9/v1"}]}))
    turns = [lambda: [ToolCallPart("load_skill", {"name": "make-it-pass"}),
                      ToolCallPart("stage_read", {"path": "tests/test_slug.py"})],
             lambda: [ToolCallPart("stage_write", {"path": "app/slug.py", "content": SLUG})],
             lambda: [TextPart("Wrote app/slug.py.")]]
    model = FunctionModel(lambda messages, info: ModelResponse(parts=turns.pop(0)()), model_name="scripted")
    actor, _ = check(config)
    outcome = run_rehearsal(config, actor, say=lambda _: None, runner=lambda t: run_cue(t, build=lambda rm: model))
    assert outcome.passed and outcome.verdicts == [("tests-pass", True, outcome.verdicts[0][2])]


def entry(model, url):
    return {"provider": "openai-compatible", "model": model, "base_url": url, "price": {"input": 1, "output": 1}}


def copy_of_examples(tmp_path, url) -> Path:
    """The docs' way: copy examples/, then point the copy's models at the fake server, and its verifiers at this
    Python's pytest (the play's own verifier commands: D35), since the suite has no network."""
    shutil.copytree(EXAMPLES, tmp_path / "examples")
    play = tmp_path / "examples/plays/slug-kata"
    doc = yaml.safe_load((play / "play.yaml").read_text())
    doc["verifiers"] = {
        "tests-fail": {"command": [PY, "-c", "import subprocess, sys; sys.exit(0 if subprocess.call("
                                              "[sys.executable, '-m', 'pytest', '-q', 'tests']) == 1 else 1)"]},
        "tests-pass": {"command": [PY, "-m", "pytest", "-q", "tests"]}}
    (play / "play.yaml").write_text(yaml.safe_dump(doc))
    for name, model in (("director", "director"), ("tester-1", "write:tests/test_slug.py"),
                        ("coder-1", "write:app/slug.py"), ("coder-2", "write:app/words.py")):
        doc = yaml.safe_load((play / f"{name}.yaml").read_text())
        doc["models"] = [entry(model, url)]
        doc["credentials"] = {k: v for k, v in doc.get("credentials", {}).items() if k.startswith("ZANNI_")}
        doc["state_dir"] = str(tmp_path / "state" / name)
        (play / f"{name}.yaml").write_text(yaml.safe_dump(doc))
    return play


def test_the_slug_kata_runs_end_to_end_from_a_copy(tmp_path):
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), "ZANNI_JOIN_TOKEN": "join-token-fake",
           "ZANNI_OWNER_TOKEN": "owner-token-fake"}
    with fake_openai() as (url, calls, scripts):
        scripts["files"].update({"tests/test_slug.py": TESTS, "app/slug.py": SLUG})
        scripts["director"] = [
            [("read", {"path": "backlog/round-1.md"})],
            [("cue", {"target": "tester", "scene": "Specify", "instructions": "Write tests/test_slug.py.",
                      "reads": ["backlog/round-1.md", "spec/"], "writes": ["tests/"]})],
            [("wait_for_reports", {})],
            [("run_verifier", {"name": "tests-fail"})],
            [("ask_gate", {"name": "plan", "summary": "Two failing tests for slugify."})],
            [("cast", {"part": "coder", "seats": 1})],
            [("cue", {"target": "coder", "scene": "Build", "instructions": "Make tests/test_slug.py pass in "
                      "app/slug.py.", "writes": ["app/"]})],
            [("wait_for_reports", {})],
            [("run_verifier", {"name": "tests-pass"})],
            [("stop", {"reason": "done"})],
            "The kata is done.",
        ]
        play = copy_of_examples(tmp_path, url)
        director = subprocess.Popen([PY, "-m", "zanni", str(play / "play.yaml")], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, env=env, stdin=subprocess.DEVNULL)
        try:
            for _ in range(450):
                shown = subprocess.run([PY, "-m", "zanni", "gate", str(play / "play.yaml")], capture_output=True,
                                       text=True, env=env)
                if "waiting at a gate" in shown.stdout:
                    break
                time.sleep(0.2)
            approved = subprocess.run([PY, "-m", "zanni", "gate", str(play / "play.yaml"), "approve"],
                                      capture_output=True, text=True, env=env)
            out, err = director.communicate(timeout=180)
        finally:
            director.kill()
    assert approved.returncode == 0, approved.stderr
    assert director.returncode == 0, out + err
    assert "tests-fail: " in out and "(from the play; timeout 300 s; runs here)" in out
    assert "The play is done." in out and "tests-pass passed" in out
    assert (play / "stage/tests/test_slug.py").read_text() == TESTS and (play / "stage/app/slug.py").read_text() == SLUG
    log = [json.loads(line) for line in next((play / "log").glob("*.jsonl")).read_text().splitlines()]
    assert [(e["verifier"], e["passed"]) for e in log if e["event"] == "verdict"] == [("tests-fail", True),
                                                                                      ("tests-pass", True)]
    assert "write:app/words.py" not in calls  # coder-2 was listed, never needed, never started
