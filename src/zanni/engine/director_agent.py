"""One turn of the director's agent (D33): a fresh model run with the director's tools, on its models in order,
falling back on each entry's reasons (D27). The tools and every rule they check are the director's own code
(src/zanni/director/); the engine only runs the loop."""

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from pydantic_ai import Agent, FunctionToolset
from pydantic_ai.models import Model

from zanni.actor.contract import AllModelsFailed, Fallback, ResolvedModel
from zanni.engine.fallback import classify
from zanni.engine.models import build_model
from zanni.engine.run import cost_of

REQUESTS_PER_TURN = 25  # model requests in one turn, so one turn can't run away; the next turn starts fresh


@dataclass
class TurnResult:
    model: str  # the model that finished the turn, as "provider model"
    output: str
    requests: int
    input_tokens: int
    output_tokens: int
    cost: Decimal | None  # every attempt's spend, failed ones included; None when any of it is unknown (D7)
    fallbacks: list[Fallback] = field(default_factory=list)


async def run_director_turn(models: list[ResolvedModel], instructions: str, prompt: Callable[[], str],
                            tools: list[Callable], *, build: Callable[[ResolvedModel], Model] = build_model,
                            requests_per_turn: int = REQUESTS_PER_TURN) -> TurnResult:
    """Run one turn. `prompt` is called for each attempt, so a fallback model sees the state as it is now.

    Raises AllModelsFailed when every model failed (the director then pauses the play, D33).
    """
    fallbacks: list[Fallback] = []
    spent: Decimal | None = Decimal(0)
    for i, rm in enumerate(models):
        agent = Agent(build(rm), instructions=instructions, toolsets=[FunctionToolset(tools, sequential=True)])
        usage = None
        output = ""
        try:
            async with agent.iter(prompt()) as run:
                async for node in run:
                    usage = run.usage
                    if usage.requests >= requests_per_turn and Agent.is_call_tools_node(node):
                        output = f"(the turn reached {requests_per_turn} model requests and was ended)"
                        break
                if run.result is not None:
                    output = str(run.result.output)
                usage = run.usage
        except Exception as exc:
            reason = classify(exc)
            if reason is None:
                raise
            spent = _add(spent, cost_of(usage, rm)[0] if usage and usage.requests else Decimal(0))
            fallbacks.append(Fallback(rm.label(), reason, f"{type(exc).__name__}: {exc}"[:300]))
            if i == len(models) - 1 or reason not in rm.entry.fall_back_on:
                raise AllModelsFailed(fallbacks) from exc
            continue
        spent = _add(spent, cost_of(usage, rm)[0])
        return TurnResult(rm.label(), output, usage.requests, usage.input_tokens, usage.output_tokens, spent, fallbacks)
    raise AllModelsFailed(fallbacks)


def _add(total: Decimal | None, amount: Decimal | None) -> Decimal | None:
    return None if total is None or amount is None else total + amount
