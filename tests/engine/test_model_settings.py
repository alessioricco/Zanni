"""D61: the director's instructions and tools are cached by a provider that supports it, and seats' aren't; a model
entry's max_output caps every response. Checked at the engine's door, with no provider call."""

import asyncio
from decimal import Decimal

from genai_prices import Usage, calc_price
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from tests.engine.fakes import MemoryStage
from zanni.actor.contract import CueTask, ResolvedModel
from zanni.engine.director_agent import run_director_turn
from zanni.engine.run import run_cue
from zanni.files.schemas import ModelEntry


def recording():
    """A model that answers at once, keeping the settings each request carried."""
    seen: list = []

    def respond(messages, info: AgentInfo) -> ModelResponse:
        seen.append(dict(info.model_settings or {}))
        return ModelResponse(parts=[TextPart("done")])

    return FunctionModel(respond, model_name="recording"), seen


def entry(provider="anthropic", **kw) -> ResolvedModel:
    return ResolvedModel(ModelEntry(provider=provider, model="claude-haiku-5-5", **kw), api_key="sk-test-fake")


CACHE = {"anthropic_cache_instructions": True, "anthropic_cache_tool_definitions": True}


def test_the_directors_instructions_and_tools_are_cached_on_anthropic():
    model, seen = recording()
    asyncio.run(run_director_turn([entry()], "the script", lambda: "the state", [], build=lambda rm: model))
    assert CACHE.items() <= seen[0].items()


def test_a_director_on_another_provider_asks_for_no_cache():
    model, seen = recording()
    local = entry("ollama", base_url="http://127.0.0.1:11434", price={"input": 0, "output": 0})
    asyncio.run(run_director_turn([local], "the script", lambda: "the state", [], build=lambda rm: model))
    assert not any(k.startswith("anthropic_cache") for k in seen[0])


def test_a_seats_cue_isnt_cached_and_max_output_reaches_every_request():
    model, seen = recording()
    task = CueTask(instructions="i", skills={}, prompt="p", stage=MemoryStage(), models=[entry(max_output=4000)])
    asyncio.run(run_cue(task, build=lambda rm: model))
    assert seen[0].get("max_tokens") == 4000 and not any(k.startswith("anthropic_cache") for k in seen[0])
    model, seen = recording()
    asyncio.run(run_director_turn([entry(max_output=1500)], "s", lambda: "x", [], build=lambda rm: model))
    assert seen[0]["max_tokens"] == 1500


def test_without_max_output_nothing_is_capped():
    model, seen = recording()
    task = CueTask(instructions="i", skills={}, prompt="p", stage=MemoryStage(), models=[entry()])
    asyncio.run(run_cue(task, build=lambda rm: model))
    assert "max_tokens" not in seen[0]


def test_cached_tokens_are_priced_at_their_own_prices():
    """The budget depends on it: genai-prices prices a cache read below plain input, and a cache write above."""
    def price(**usage) -> Decimal:
        return calc_price(Usage(output_tokens=100, **usage), model_ref="claude-haiku-5-5",
                          provider_id="anthropic").total_price

    plain = price(input_tokens=10_000)
    assert price(input_tokens=10_000, cache_read_tokens=9_000) < plain < price(input_tokens=10_000,
                                                                               cache_write_tokens=9_000)
