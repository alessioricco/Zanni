"""The opt-in text tool format, for models without native tool calling (D5).

Pydantic AI has no fallback of its own: a request with tools fails on such a model. This wrapper sends the model
no tools. It describes them in the prompt, replays earlier tool calls and results as text, and parses ```tool
blocks in the reply back into tool calls, so the agent loop, the toolsets and the stage's checks run unchanged.
Proved in the spike (docs/spikes/pydantic-ai.md, item 4); this version closes the gaps the spike listed.
"""

import json
import re
import uuid
from dataclasses import replace

from pydantic_ai.messages import (
    ModelMessage, ModelRequest, ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart,
)
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

BLOCK = re.compile(r"```tool\s*\n?(.*?)```", re.DOTALL)
MAX_REPAIRS = 2  # times a malformed tool block is sent back to the model within one request


def describe(params: ModelRequestParameters) -> str:
    lines = ["You can call tools. To call one, reply with a fenced block like this, then stop and wait for the result:",
             '```tool\n{"tool": "<name>", "args": {...}}\n```',
             "You may put several blocks in one reply; they run in order.",
             "When you need no more tools, reply with your final answer as plain text, without a tool block.", "",
             "Tools:"]
    for t in params.function_tools:
        lines.append(f"- {t.name}: {t.description or ''} Arguments (JSON Schema): {json.dumps(t.parameters_json_schema)}")
    return "\n".join(lines)


def as_text(messages: list[ModelMessage], tool_help: str) -> list[ModelMessage]:
    """Replay a conversation with tool calls and results as plain text; the tool help goes in the first request."""
    out: list[ModelMessage] = []
    for i, m in enumerate(messages):
        if isinstance(m, ModelResponse):
            parts = [TextPart(f'```tool\n{json.dumps({"tool": p.tool_name, "args": p.args_as_dict()})}\n```')
                     if isinstance(p, ToolCallPart) else p for p in m.parts]
            out.append(replace(m, parts=parts))
            continue
        parts = []
        for p in m.parts:
            if isinstance(p, ToolReturnPart):
                parts.append(UserPromptPart(f"Result of {p.tool_name}:\n{p.model_response_str()}"))
            elif isinstance(p, RetryPromptPart):
                parts.append(UserPromptPart(p.model_response()))
            else:
                parts.append(p)
        if i == 0:
            parts.insert(0, UserPromptPart(tool_help))
        out.append(replace(m, parts=parts))
    return out


def loads_lenient(block: str):
    """json.loads, but close braces and brackets a small model left open (seen with gemma3:4b in milestone 2)."""
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        stack, in_string, escaped = [], False, False
        for ch in block:
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]" and stack:
                stack.pop()
        if in_string or not stack:
            raise
        return json.loads(block.rstrip() + "".join(reversed(stack)))


def parse(response: ModelResponse) -> tuple[list[ToolCallPart], list[str]]:
    """The tool calls in a reply, and a problem for each block that couldn't be read."""
    text = "".join(p.content for p in response.parts if isinstance(p, TextPart))
    calls, problems = [], []
    for n, block in enumerate(BLOCK.findall(text), start=1):
        try:
            call = loads_lenient(block)
            if not isinstance(call, dict) or not isinstance(call.get("tool"), str):
                raise ValueError('it needs a "tool" name')
            args = call.get("args", {})
            if not isinstance(args, dict):
                raise ValueError('"args" must be an object')
        except (json.JSONDecodeError, ValueError) as e:
            problems.append(f"tool block {n} isn't valid: {e}")
            continue
        calls.append(ToolCallPart(call["tool"], args, tool_call_id=f"text-{uuid.uuid4().hex[:8]}"))
    return calls, problems


class TextToolsModel(WrapperModel):
    async def request(self, messages: list[ModelMessage], model_settings: ModelSettings | None,
                      model_request_parameters: ModelRequestParameters) -> ModelResponse:
        params = model_request_parameters
        if not params.function_tools:
            return await super().request(messages, model_settings, params)
        if params.output_tools:
            raise NotImplementedError("the text tool format supports text output only")
        plain = replace(params, function_tools=[])
        history = as_text(messages, describe(params))
        usage = None
        for _ in range(MAX_REPAIRS + 1):
            response = await self.wrapped.request(history, model_settings, plain)
            usage = response.usage if usage is None else usage + response.usage
            calls, problems = parse(response)
            if not problems:
                return replace(response, parts=calls, usage=usage) if calls else replace(response, usage=usage)
            # Tell the model what was wrong, instead of dropping the block silently.
            history = [*history, response, ModelRequest(parts=[UserPromptPart(
                "; ".join(problems) + '. Reply again, with each tool call as a ```tool block holding '
                '{"tool": "<name>", "args": {...}}, or with plain text if you are done.')])]
        return replace(response, usage=usage)  # still malformed after the repairs: the text goes back as it is
