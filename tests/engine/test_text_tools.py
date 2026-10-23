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
