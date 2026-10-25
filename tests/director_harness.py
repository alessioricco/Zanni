"""A small play on loopback, for the director's tests: a tester and up to two coders, scripted actors joining over
A2A, and the director's agent driven by a scripted model (FunctionModel), so every turn is known."""

import asyncio
import shutil
import sys
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from zanni.actor.contract import ResolvedModel
from zanni.actor.roles import load_role
from zanni.actor.seat import play_seat
from zanni.stage import folder_stage
from zanni.director.casting import Director, PartSlot
from zanni.director.contract import DirectorInfo
from zanni.director.gates import Gates
from zanni.director.play import Production, TurnOutcome
from zanni.director.prompt import instructions
from zanni.director.state import PlayState
from zanni.engine.director_agent import run_director_turn
from zanni.engine.run import run_cue
from zanni.engine.serve import serving
from zanni.files.check import verifier_commands
from zanni.files.schemas import ActorConfiguration, ModelEntry, PlayFile, Script
from zanni.log import Log

EXAMPLES = Path(__file__).parents[1] / "examples"
TOKEN = "join-token-fake"
PY = sys.executable
TESTS_FAIL = [PY, "-c", "import pathlib, sys; sys.exit(0 if pathlib.Path('tests/test_slug.py').exists() "
                        "and not pathlib.Path('app/slug.py').exists() else 1)"]
TESTS_PASS = [PY, "-c", "import pathlib, sys; sys.exit(0 if pathlib.Path('app/slug.py').exists() else 1)"]
PROSE = """# Slug kata

## Act 1: a round
The **tester** writes a failing test for each item in `backlog/round-1.md`. *Verifier:* `tests-fail`.
**Gate: plan.** Then each **coder** makes the tests pass. *Verifier:* `tests-pass`.
"""


def priced(name="scripted", per_million=1) -> ResolvedModel:
    return ResolvedModel(ModelEntry(provider="openai-compatible", model=name, base_url="http://127.0.0.1:9/v1",
                                    price={"input": per_million, "output": per_million}))


def kata(tmp_path: Path, *, gates=("plan",), budget=None, turns=30, max_rounds=2, done_when=("tests-pass",),
         coder_seats="1-2", gate_timeout=None):
    """The roles, the stage, the script and the play, in tmp_path."""
    shutil.copytree(EXAMPLES / "roles/slug-tester", tmp_path / "roles/tester")
    coder = tmp_path / "roles/coder"
    coder.mkdir(parents=True)
    (coder / "role.yaml").write_text("name: coder\nversion: 0.1.0\nmission: Make the tests pass.\n"
                                     "needs:\n  stage_read: [backlog/, spec/, tests/]\n  stage_write: [app/]\n")
    (coder / "AGENTS.md").write_text("# Coder\n\nYou make the tests pass.\n")
    stage = tmp_path / "stage"
    shutil.copytree(EXAMPLES / "roles/slug-tester/rehearsals/smoke-stage", stage)
    (stage / "app/slug.py").unlink()
    script = Script.model_validate({
        "name": "kata", "version": "1.0.0", "mission": "Make the slug tests pass.",
        "parts": {"tester": {"writes": ["tests/"]}, "coder": {"seats": coder_seats, "writes": ["app/"]}},
        "stage": {"expects": ["backlog/round-1.md"]}, "gates": ["plan"],
        "verifiers": {"tests-fail": {"description": "every new test fails", "command": TESTS_FAIL},
                      "tests-pass": {"description": "every test passes", "command": TESTS_PASS}},
        "stop": {"max_rounds": max_rounds, "done_when": list(done_when)}})
    play = PlayFile.model_validate({
        "name": "kata", "script": "./kata", "stage": "./stage",
        "cast": {"tester": "./roles/tester", "coder": "./roles/coder"},
        "house_rules": {"gates": list(gates), "budget": budget, "max_director_turns": turns,
                        "gate_timeout": gate_timeout}})
    return play, script, stage


def production(tmp_path, play, script, stage, *, say=lambda _: None, interval=2):
    def fits(want: str):
        return lambda card: None if card.role.name == want else ("role-mismatch", f"this part is for {want}")

    parts = [PartSlot(name, fits(load_role(tmp_path / f"roles/{name}").manifest.name), script.parts[name].seats.max)
             for name in play.cast]
    log = Log(tmp_path / "log.jsonl", "r1")
    casting = Director(join_token=TOKEN, parts=parts, stage=folder_stage(stage), log=log,
                       heartbeat_interval=interval, say=say)
    state = PlayState(play, script)
    gates = Gates(state, log, play.house_rules.gate_timeout, say=say)
    return Production(state=state, casting=casting, stage=casting.stage, log=log,
                      verifiers=verifier_commands(play, script), gates=gates, say=say)


class Steps:
    """A scripted director model: each call returns the next response. A text response ends a turn."""

    def __init__(self, steps: list):
        self.steps = list(steps)
        self.seen: list[str] = []  # every tool result and turn prompt the model received, in order

    def __call__(self, messages, info):
        for part in messages[-1].parts:
            if isinstance(part, ToolReturnPart):
                self.seen.append(f"{part.tool_name}: {part.content}")
            elif isinstance(part, UserPromptPart):
                self.seen.append(f"prompt: {part.content}")
        step = self.steps.pop(0) if self.steps else "end"
        if callable(step):
            step = step(messages)
        if isinstance(step, str):
            return ModelResponse(parts=[TextPart(step)])
        return ModelResponse(parts=[ToolCallPart(name, args) for name, args in step])


def run_turn(p: Production, steps: Callable, models=None, build=None) -> Callable:
    """The director's turn, as the command wires it: the engine runs the model loop with the director's tools."""
    text = instructions(p.state.script, PROSE, p.state.play)
    model = FunctionModel(steps, model_name="scripted-director")

    async def turn(prompt):
        result = await run_director_turn(models or [priced()], text, prompt, p.tools(), build=build or (lambda rm: model),
                                         spending=p.director_spending, end_turn=p.turn_should_end,
                                         requests_per_turn=p.state.play.house_rules.requests_per_turn)
        return TurnOutcome(result.model, result.cost, result.requests, result.fallbacks)

    return turn


def actor_runner(files: dict[str, str], summary: str = "Done.", cost_per_token=None):
    """A scripted actor: writes `files` on the stage, then answers `summary`."""

    def respond(messages, info):
        if files and not any(isinstance(p, ToolReturnPart) for m in messages for p in m.parts):
            return ModelResponse(parts=[ToolCallPart("stage_write", {"path": k, "content": v}) for k, v in files.items()])
        return ModelResponse(parts=[TextPart(summary)])

    model = FunctionModel(respond, model_name="scripted-actor")
    return lambda task: run_cue(task, build=lambda rm: model)


async def actor(url, tmp_path, part, runner, *, name=None, models=None, servers=None):
    role = load_role(tmp_path / f"roles/{part}")
    config = ActorConfiguration.model_validate({"name": name or f"{part}-actor", "role": f"./roles/{part}",
                                                "play": url, "models": [{"provider": "ollama", "model": "m"}]})
    return await play_seat(url, config, role, models or [priced("actor")], servers or [], join_token=TOKEN,
                           log_at=lambda play: tmp_path / f"actors/{name or part}.jsonl", run_id="r1",
                           say=lambda _: None, runner=runner)


async def until(condition, timeout=20):
    for _ in range(int(timeout / 0.02)):
        if condition():
            return
        await asyncio.sleep(0.02)
    raise TimeoutError("the condition never held")


async def staged(p: Production, actors: list[tuple[str, Callable]], tmp_path, body):
    """Serve the production, join the actors, wait until each part has its seat, then run `body(p)`."""
    info = DirectorInfo(name="d", description="test", version="0", play=p.state.play.name, script="./kata")
    async with serving(p.casting, info) as server:
        seats = [asyncio.create_task(actor(server.url, tmp_path, part, runner, name=f"{part}-{i}"))
                 for i, (part, runner) in enumerate(actors, start=1)]
        await until(lambda: len(p.active_seats()) == len(actors))
        try:
            return await body(p)
        finally:
            for seat in p.active_seats():
                await p.casting.release(seat, "play-stopped")
            await asyncio.gather(*seats, return_exceptions=True)


def money(text: str) -> Decimal:
    return Decimal(text)
