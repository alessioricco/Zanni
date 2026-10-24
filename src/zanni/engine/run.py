"""Run one cue on an actor's models, in order, falling back on each entry's reasons (D11, D20)."""

from collections.abc import Callable
from decimal import Decimal

from pydantic_ai import Agent
from pydantic_ai.models import Model

from zanni.actor.contract import AllModelsFailed, CueResult, CueTask, Fallback, ResolvedModel
from zanni.engine.fallback import classify
from zanni.engine.mcp import mcp_toolsets
from zanni.engine.models import build_model
from zanni.engine.tools import skill_toolset, stage_toolset

MILLION = Decimal(1_000_000)


def cost_of(usage, rm: ResolvedModel) -> tuple[Decimal | None, str]:
    """Published prices first (genai-prices, through Pydantic AI), then the entry's own price, else unknown (D7)."""
    if usage.cost is not None:
        return usage.cost, "genai-prices"
    price = rm.entry.price
    if price is None:
        return None, "unknown"
    return price.input * usage.input_tokens / MILLION + price.output * usage.output_tokens / MILLION, "configuration"


async def run_cue(task: CueTask, *, build: Callable[[ResolvedModel], Model] = build_model) -> CueResult:
    fallbacks: list[Fallback] = []
    for i, rm in enumerate(task.models):
        agent = Agent(build(rm), instructions=task.instructions,
                      toolsets=[skill_toolset(task.skills), stage_toolset(task.stage), *mcp_toolsets(task.mcp_servers)])
        try:
            result = await agent.run(task.prompt)
        except Exception as exc:
            reason = classify(exc)
            if reason is None:
                raise
            fallbacks.append(Fallback(rm.label(), reason, f"{type(exc).__name__}: {exc}"[:300]))
            last = i == len(task.models) - 1
            if last or reason not in rm.entry.fall_back_on:
                raise AllModelsFailed(fallbacks) from exc
            continue  # work already written stays on the stage; the next model sees it
        usage = result.usage
        cost, source = cost_of(usage, rm)
        calls = [p.tool_name for m in result.all_messages() for p in m.parts if p.part_kind == "tool-call"]
        return CueResult(output=str(result.output), model=rm.label(), provider=rm.entry.provider,
                         model_name=rm.entry.model, tool_calls=calls,
                         input_tokens=usage.input_tokens, output_tokens=usage.output_tokens, requests=usage.requests,
                         cost=cost, cost_source=source, fallbacks=fallbacks)
    raise AllModelsFailed(fallbacks)
