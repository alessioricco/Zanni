"""D5: the text tool format, driven by a scripted model that only ever sees text."""

import asyncio

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from tests.engine.fakes import MemoryStage, entry
from zanni.actor.contract import CueTask
from zanni.engine.run import run_cue
from zanni.engine.text_tools import TextToolsModel, parse

WRITE = '```tool\n{"tool": "stage_write", "args": {"path": "tests/%s.py", "content": "x"}}\n```'


def text_model(*replies):
    replies = list(replies)
    seen: list[AgentInfo] = []

    def respond(messages, info: AgentInfo) -> ModelResponse:
        seen.append(info)
        return ModelResponse(parts=[TextPart(replies.pop(0))])

    return TextToolsModel(FunctionModel(respond)), seen


def run(model, stage):
    t = CueTask(instructions="tester", skills={}, prompt="write tests", stage=stage, models=[entry(tool_format="text")])
    return asyncio.run(run_cue(t, build=lambda rm: model))


def test_the_model_is_sent_no_tools_and_tool_blocks_become_calls():
    stage = MemoryStage()
    model, seen = text_model(WRITE % "a", "Done.")
    result = run(model, stage)
    assert "tests/a.py" in stage.files and result.output == "Done."
    assert all(not info.function_tools for info in seen)


def test_several_blocks_in_one_reply_run_in_order():
    stage = MemoryStage()
    model, _ = text_model("Writing both.\n" + WRITE % "a" + "\n" + WRITE % "b", "Done.")
    run(model, stage)
    assert [p for p, _ in stage.log] == ["tests/a.py", "tests/b.py"]


def test_a_malformed_block_is_sent_back_to_the_model():
    stage = MemoryStage()
    model, seen = text_model('```tool\n{"tool": "stage_write", "args": {"path": }\n```', WRITE % "a", "Done.")
    run(model, stage)
    assert "tests/a.py" in stage.files
    assert len(seen) == 3  # the bad reply, the repaired one, the final answer


def test_parse_reports_each_problem():
    calls, problems = parse(ModelResponse(parts=[TextPart('```tool\n{"args": {}}\n```\n```tool\nnot json\n```')]))
    assert calls == [] and len(problems) == 2
    assert 'it needs a "tool" name' in problems[0]


def test_a_block_missing_its_closing_braces_is_closed():
    """gemma3:4b left the outer brace off in a recorded run (docs/runs/milestone-2.md)."""
    block = r'{"tool": "stage_write", "args": {"path": "tests/a.py", "content": "x = \"}\"\n"}'
    calls, problems = parse(ModelResponse(parts=[TextPart(f"```tool\n{block}\n```")]))
    assert problems == [] and calls[0].args_as_dict() == {"path": "tests/a.py", "content": 'x = "}"\n'}


def test_an_unterminated_string_is_still_reported():
    calls, problems = parse(ModelResponse(parts=[TextPart('```tool\n{"tool": "stage_write", "args": {"path": "a\n```')]))
    assert calls == [] and len(problems) == 1


def test_a_final_reply_that_is_still_a_broken_tool_block_is_a_failure():
    """gemma3:4b looped inside a tool block until its output limit, in a recorded run; that must not count as done."""
    import pytest
    from zanni.actor.contract import AllModelsFailed
    broken = '```tool\n{"tool": "stage_write", "args": {"path": "tests/a.py", "content": "' + "\\n" * 50 + '\n```'
    model, _ = text_model(broken, broken, broken)
    with pytest.raises(AllModelsFailed, match="couldn't write correctly"):
        run(model, MemoryStage())
