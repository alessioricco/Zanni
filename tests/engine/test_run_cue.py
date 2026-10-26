import asyncio

import pytest
from pydantic_ai.exceptions import ModelContextWindowExceededError, ModelHTTPError, ModelRateLimitError

from tests.engine.fakes import MemoryStage, entry, scripted
from zanni.actor.contract import AllModelsFailed, CueTask
from zanni.engine.fallback import classify
from zanni.engine.run import run_cue
from zanni.files.schemas import Price


def task(stage, *models, skills=None):
    return CueTask(instructions="You are a tester.", skills=skills or {"write-test": "# Write a test"},
                   prompt="Write tests/test_a.py.", stage=stage, models=list(models))


def run(t, builds):
    builds = list(builds)
    return asyncio.run(run_cue(t, build=lambda rm: builds.pop(0)))


def test_a_cue_runs_tools_and_reports_cost_from_the_configuration():
    stage = MemoryStage({"spec.md": "AC1"})
    model = scripted({"load_skill": {"name": "write-test"}, "stage_read": {"path": "spec.md"}},
                     {"stage_write": {"path": "tests/test_a.py", "content": "def test_a(): pass\n"}},
                     "Wrote tests/test_a.py.")
    result = run(task(stage, entry(price=Price(input=1, output=2))), [model])
    assert result.output == "Wrote tests/test_a.py."
    assert result.tool_calls == ["load_skill", "stage_read", "stage_write"]
    assert stage.files["tests/test_a.py"] == "def test_a(): pass\n"
    assert result.cost_source == "configuration" and result.cost is not None
    assert result.model == "ollama m"


def test_unknown_cost_stays_unknown():
    result = run(task(MemoryStage(), entry()), [scripted("done")])
    assert result.cost is None and result.cost_source == "unknown"


def test_a_refused_stage_write_goes_back_to_the_model():
    stage = MemoryStage()
    model = scripted({"stage_write": {"path": "app/x.py", "content": "x"}},
                     {"stage_write": {"path": "tests/x.py", "content": "x"}}, "ok")
    run(task(stage, entry()), [model])
    assert "app/x.py" not in stage.files and "tests/x.py" in stage.files


def test_a_stage_refusal_goes_back_to_the_model_more_than_once():
    """A wrong path asked for twice in a row is two refusals the model reads, not a cue that fails."""
    stage = MemoryStage({"spec.md": "AC1"})
    model = scripted({"stage_read": {"path": "nope.md"}}, {"stage_read": {"path": "still-nope.md"}},
                     {"stage_read": {"path": "spec.md"}}, "Read spec.md.")
    result = run(task(stage, entry()), [model])
    assert result.output == "Read spec.md."


def test_rate_limit_falls_back_to_the_next_model():
    first = scripted(ModelRateLimitError("m", "slow down"), name="first")
    result = run(task(MemoryStage(), entry("first"), entry("second")), [first, scripted("done", name="second")])
    assert result.model == "ollama second"
    assert [(f.model, f.reason) for f in result.fallbacks] == [("ollama first", "rate-limit")]


def test_a_reason_the_entry_doesnt_list_stops_the_cue():
    first = scripted(ModelContextWindowExceededError("m", "too long"))
    t = task(MemoryStage(), entry("first", fall_back_on=["error"]), entry("second"))
    with pytest.raises(AllModelsFailed, match="ollama first: context"):
        run(t, [first, scripted("never")])


def test_the_last_model_failing_reports_every_attempt():
    t = task(MemoryStage(), entry("a"), entry("b"))
    with pytest.raises(AllModelsFailed) as e:
        run(t, [scripted(ModelHTTPError(500, "a")), scripted(ModelHTTPError(503, "b"))])
    assert [f.reason for f in e.value.fallbacks] == ["error", "error"]


@pytest.mark.parametrize("exc, reason", [
    (ModelRateLimitError("m", "x"), "rate-limit"),
    (ModelContextWindowExceededError("m", "x"), "context"),
    (ModelHTTPError(400, "m", {"message": "does not support tools"}), "error"),
    (TimeoutError(), "timeout"),
    (ValueError("a bug"), None),
])
def test_classify(exc, reason):
    assert classify(exc) == reason
