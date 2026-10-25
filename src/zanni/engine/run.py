"""Run one cue on an actor's models, in order, falling back on each entry's reasons (D11, D20)."""

from collections.abc import Callable
from decimal import Decimal

from pydantic_ai import Agent
from pydantic_ai.models import Model

from zanni.actor.contract import AllModelsFailed, CueResult, CueTask, Fallback, ResolvedModel, StageError, StageUnavailable
from zanni.engine.fallback import UnusableReply, classify
from zanni.engine.mcp import mcp_toolsets
from zanni.engine.models import build_model
from zanni.engine.text_tools import BLOCK
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
    """Run the cue on each model in turn. With a budget, the spend is checked after every model response, across
    attempts, and the run stops once it reaches the budget: overshoot is bounded by one model call (D39)."""
    fallbacks: list[Fallback] = []
    spent = Decimal(0)  # failed attempts' spend counts against the cue's budget too
    for i, rm in enumerate(task.models):
        agent = Agent(build(rm), instructions=task.instructions,
                      toolsets=[skill_toolset(task.skills), stage_toolset(task.stage), *mcp_toolsets(task.mcp_servers)])
        usage, over, output, messages = None, False, "", []
        try:
            async with agent.iter(task.prompt) as run:
                async for node in run:
                    usage = run.usage
                    if task.budget is not None and Agent.is_call_tools_node(node):
                        cost = cost_of(usage, rm)[0]
                        if cost is not None and spent + cost >= task.budget:
                            over = True
                            break
                usage, messages = run.usage, run.all_messages()
                if run.result is not None:
                    output = str(run.result.output)
            if not over and rm.entry.tool_format == "text" and BLOCK.search(output):
                # The model's last reply still holds a tool block it never got right: that is a failed answer.
                raise UnusableReply("the model's last reply still held a tool block it couldn't write correctly")
        except StageError as exc:
            if exc.code != "unavailable":
                raise
            if usage is not None and usage.requests:
                cost = cost_of(usage, rm)[0]
                spent = None if cost is None else spent + cost
            raise StageUnavailable(f"the stage stopped answering: {exc}", spent) from exc
        except Exception as exc:
            reason = classify(exc)
            if reason is None:
                raise
            if usage is not None and usage.requests:
                spent += cost_of(usage, rm)[0] or 0
            fallbacks.append(Fallback(rm.label(), reason, f"{type(exc).__name__}: {exc}"[:300]))
            last = i == len(task.models) - 1
            if last or reason not in rm.entry.fall_back_on:
                raise AllModelsFailed(fallbacks) from exc
            continue  # work already written stays on the stage; the next model sees it
        cost, source = cost_of(usage, rm)
        if cost is not None:
            cost += spent
        calls = [p.tool_name for m in messages for p in m.parts if p.part_kind == "tool-call"]
        if over:
            output = f"Stopped at the cue's budget of ${task.budget}, after spending ${cost}."
        return CueResult(output=output, model=rm.label(), provider=rm.entry.provider,
                         model_name=rm.entry.model, tool_calls=calls,
                         input_tokens=usage.input_tokens, output_tokens=usage.output_tokens, requests=usage.requests,
                         cost=cost, cost_source=source, fallbacks=fallbacks, over_budget=over)
    raise AllModelsFailed(fallbacks)
