"""Run one cue on an actor's models, in order, falling back on each entry's reasons (D11, D20)."""

from collections.abc import Callable
from decimal import Decimal

from pydantic_ai import Agent
from pydantic_ai.models import Model

from zanni.actor.contract import (
    AllModelsFailed, CueResult, CueTask, Fallback, McpServerSpec, ResolvedModel, StageError, StageUnavailable,
)
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


def tool_calls(messages) -> list[str]:
    return [p.tool_name for m in messages for p in m.parts if p.part_kind == "tool-call"]


def tool_returns(messages) -> list[str]:
    """The tool calls that ran and returned: a call the run stopped before running is never charged."""
    return [p.tool_name for m in messages for p in m.parts if p.part_kind == "tool-return"]


def brought_charges(calls: list[str], servers: list[McpServerSpec]) -> tuple[Decimal | None, int]:
    """What the calls to tools the actor brought cost, at their declared prices, and how many there were (D53).
    A call to one with no price makes the charge unknown, never zero (D7)."""
    brought = sorted((s for s in servers if s.brought), key=lambda s: -len(s.name))  # the longest prefix wins
    total: Decimal | None = Decimal(0)
    count = 0
    for call in calls:
        server = next((s for s in brought if call.startswith(f"{s.name}_")), None)
        if server is None:
            continue
        count += 1
        total = None if total is None or server.price is None else total + server.price
    return total, count


def add(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    return None if a is None or b is None else a + b


async def run_cue(task: CueTask, *, build: Callable[[ResolvedModel], Model] = build_model) -> CueResult:
    """Run the cue on each model in turn. With a budget, the spend is checked after every model response, across
    attempts, and the run stops once it reaches the budget: overshoot is bounded by one model call (D39)."""
    fallbacks: list[Fallback] = []
    spent: Decimal | None = Decimal(0)  # failed attempts' spend counts against the cue's budget too; None: unknown
    charged = 0  # calls to tools the actor brought, across attempts (D53)
    for i, rm in enumerate(task.models):
        agent = Agent(build(rm), instructions=task.instructions,
                      toolsets=[skill_toolset(task.skills), stage_toolset(task.stage), *mcp_toolsets(task.mcp_servers)])
        usage, over, output, messages = None, False, "", []
        try:
            async with agent.iter(task.prompt) as run:
                async for node in run:
                    usage, messages = run.usage, run.all_messages()
                    if task.budget is not None and Agent.is_call_tools_node(node):
                        cost = add(add(cost_of(usage, rm)[0], spent), brought_charges(tool_returns(messages),
                                                                                      task.mcp_servers)[0])
                        if cost is not None and cost >= task.budget:
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
                spent = add(spent, cost_of(usage, rm)[0])
            spent = add(spent, brought_charges(tool_returns(messages), task.mcp_servers)[0])
            raise StageUnavailable(f"the stage stopped answering: {exc}", spent) from exc
        except Exception as exc:
            reason = classify(exc)
            if reason is None:
                raise
            if usage is not None and usage.requests and spent is not None:
                spent += cost_of(usage, rm)[0] or 0
            charge, n = brought_charges(tool_returns(messages), task.mcp_servers)
            spent, charged = add(spent, charge), charged + n
            fallbacks.append(Fallback(rm.label(), reason, f"{type(exc).__name__}: {exc}"[:300]))
            last = i == len(task.models) - 1
            if last or reason not in rm.entry.fall_back_on:
                raise AllModelsFailed(fallbacks) from exc
            continue  # work already written stays on the stage; the next model sees it
        cost, source = cost_of(usage, rm)
        calls = tool_calls(messages)
        charge, n = brought_charges(tool_returns(messages), task.mcp_servers)
        cost = add(add(cost, spent), charge)
        if over:
            output = f"Stopped at the cue's budget of ${task.budget}, after spending ${cost}."
        return CueResult(output=output, model=rm.label(), provider=rm.entry.provider,
                         model_name=rm.entry.model, tool_calls=calls,
                         input_tokens=usage.input_tokens, output_tokens=usage.output_tokens, requests=usage.requests,
                         cost=cost, cost_source=source, fallbacks=fallbacks, over_budget=over,
                         brought_calls=charged + n)
    raise AllModelsFailed(fallbacks)
