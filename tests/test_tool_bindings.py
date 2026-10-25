"""D53: an actor brings its own tools, as it brings its own models: a binding replaces the role's server, works in
the workspace's folder, and charges its declared price per call; an unpriced one is refused under a budget."""

import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from tests.director_harness import actor, actor_runner, kata, production, until
from tests.engine.fakes import MemoryStage, scripted
from zanni.actor.contract import CueTask, McpServerSpec, ResolvedModel
from zanni.actor.mcp_config import mcp_servers
from zanni.actor.resolve import Unresolved
from zanni.director.contract import DirectorInfo
from zanni.engine.run import run_cue
from zanni.engine.serve import serving
from zanni.files.check import check
from zanni.files.schemas import ModelEntry, ToolBinding
from zanni.files.summary import summarise

ECHO = Path(__file__).parent / "engine" / "echo_mcp.py"


def role_with(tmp_path, **servers) -> Path:
    (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": servers}))
    return tmp_path


def binding(**kw) -> ToolBinding:
    return ToolBinding.model_validate(kw)


def free() -> ResolvedModel:
    return ResolvedModel(ModelEntry(provider="ollama", model="m", price={"input": 0, "output": 0}),
                         base_url="http://localhost:11434")


def test_a_binding_replaces_the_roles_server_and_the_others_stay(tmp_path):
    folder = role_with(tmp_path, **{"coding-engine": {"command": "zanni:workspace"}, "docs": {"url": "http://d/mcp"}})
    servers = mcp_servers(folder, {"ENGINE_KEY": "k-from-credentials"}, env={}, needs=["coding-engine", "docs"],
                          bindings={"coding-engine": binding(command="my-engine", args=["--key", "${ENGINE_KEY}"],
                                                             price={"per_call": "0.05"})})
    by_name = {s.name: s for s in servers}
    assert by_name["docs"].url == "http://d/mcp" and not by_name["docs"].brought
    engine = by_name["coding-engine"]
    assert (engine.command, engine.args, engine.brought, engine.price) == (
        "my-engine", ["--key", "k-from-credentials"], True, Decimal("0.05"))


def test_without_a_binding_the_roles_server_is_used(tmp_path):
    folder = role_with(tmp_path, docs={"url": "http://d/mcp"})
    [server] = mcp_servers(folder, {}, env={}, needs=["docs"])
    assert server.url == "http://d/mcp" and not server.brought and not server.unpriced


def test_the_built_in_workspace_runs_with_the_allowed_commands_and_no_secrets(tmp_path):
    """D52: zanni:workspace becomes a process serving the seat's folder; a command it runs can't read the keys."""
    folder = role_with(tmp_path, workspace={"command": "zanni:workspace"})
    ws = tmp_path / "ws"
    [server] = mcp_servers(folder, {}, env={"PATH": "/bin", "ANTHROPIC_API_KEY": "sk-x", "ZANNI_JOIN_TOKEN": "t"},
                           needs=["workspace"], workspace=ws, commands=["uv", "pytest"])
    assert server.command == sys.executable and not server.brought
    assert server.args == ["-m", "zanni.engine.workspace_server", "--folder", str(ws),
                           "--command", "uv", "--command", "pytest"]
    assert server.env == {"PATH": "/bin"} and server.cwd == str(ws)
    with pytest.raises(Unresolved, match="needs a workspace"):
        mcp_servers(folder, {}, env={}, needs=["workspace"])


def test_a_binding_for_a_tool_the_role_doesnt_need_is_refused(tmp_path):
    folder = role_with(tmp_path, workspace={"command": "zanni:workspace"})
    with pytest.raises(Unresolved, match="binds browser, which the role doesn't need; .*: workspace"):
        mcp_servers(folder, {}, env={}, needs=["workspace"], bindings={"browser": binding(command="b")})


def test_a_brought_server_runs_in_the_workspace_and_names_it(tmp_path):
    folder = role_with(tmp_path)
    workspace = tmp_path / "ws"
    [server] = mcp_servers(folder, {}, env={}, needs=["coding-engine"], workspace=workspace,
                           bindings={"coding-engine": binding(command="e", args=["--folder", "${ZANNI_WORKSPACE}"])})
    assert server.args == ["--folder", str(workspace)] and server.cwd == str(workspace)
    with pytest.raises(Unresolved, match="ZANNI_WORKSPACE"):  # no workspace: nothing to name
        mcp_servers(folder, {}, env={}, needs=["coding-engine"], bindings={"coding-engine": binding(
            command="e", args=["${ZANNI_WORKSPACE}"])})


def echo(price: str | None) -> McpServerSpec:
    return McpServerSpec(name="echo", command=sys.executable, args=[str(ECHO)], brought=True,
                         price=Decimal(price) if price is not None else None)


def cue(servers, budget=None) -> CueTask:
    return CueTask(instructions="i", skills={}, prompt="p", stage=MemoryStage(), models=[free()],
                   mcp_servers=servers, budget=budget)


def test_each_call_to_a_brought_tool_adds_its_price_to_the_cues_cost():
    model = scripted({"echo_say": {"text": "a"}}, {"echo_say": {"text": "b"}}, "done")
    result = asyncio.run(run_cue(cue([echo("0.25")]), build=lambda rm: model))
    assert result.brought_calls == 2 and result.cost == Decimal("0.50")


def test_a_call_to_an_unpriced_brought_tool_makes_the_cost_unknown_never_zero():
    model = scripted({"echo_say": {"text": "a"}}, "done")
    result = asyncio.run(run_cue(cue([echo(None)]), build=lambda rm: model))
    assert result.brought_calls == 1 and result.cost is None


def test_a_brought_tools_price_counts_against_the_cues_budget():
    model = scripted({"echo_say": {"text": "a"}}, {"echo_say": {"text": "b"}}, "done")
    result = asyncio.run(run_cue(cue([echo("1.00")], budget=Decimal("0.50")), build=lambda rm: model))
    assert result.over_budget and result.brought_calls == 1 and result.cost == Decimal("1.00")


def test_an_actor_with_an_unpriced_brought_tool_is_refused_under_a_budget_and_accepted_without(tmp_path):
    unpriced_engine = McpServerSpec(name="coding-engine", command="never-started", brought=True)

    async def join(budget):
        folder = tmp_path / ("with" if budget else "without")
        play, script, stage = kata(folder, gates=(), budget=budget)
        p = production(folder, play, script, stage)
        p.casting.require_pricing = budget is not None
        info = DirectorInfo(name="d", description="t", version="0", play="kata", script="./kata")
        async with serving(p.casting, info) as server:
            task = asyncio.create_task(actor(server.url, folder, "coder", actor_runner({}),
                                             servers=[unpriced_engine]))
            await until(lambda: task.done() or p.active_seats())
            await p.finish()
            return await task

    refused = asyncio.run(join(Decimal("1.00")))
    assert refused.exit_code == 2 and refused.reason == "unpriced"
    accepted = asyncio.run(join(None))
    assert accepted.seat == "coder-1" and accepted.reason == "play-stopped"


def test_a_bindings_credential_never_shows(tmp_path):
    role = tmp_path / "roles/worker"
    role.mkdir(parents=True)
    (role / "role.yaml").write_text("name: worker\nversion: 0.1.0\nmission: m\nneeds:\n  tools: [coding-engine]\n")
    config = tmp_path / "worker.yaml"
    config.write_text("role: ./roles/worker\nplay: http://127.0.0.1:9\n"
                      "models:\n  - { provider: ollama, model: m }\n"
                      "tools:\n  coding-engine:\n    command: e\n    env: { ENGINE_API_KEY: \"${ENGINE_API_KEY}\" }\n"
                      "credentials:\n  ENGINE_API_KEY: sk-test-not-a-real-key\n")
    config.chmod(0o600)
    doc, notes = check(config)
    shown = "\n".join(summarise(doc) + notes)
    assert "coding-engine" in shown and "ENGINE_API_KEY (stored, hidden)" in shown
    assert "sk-test-not-a-real-key" not in shown


def test_a_call_the_budget_stopped_before_it_ran_is_never_charged():
    dear = ResolvedModel(ModelEntry(provider="ollama", model="m", price={"input": 1_000_000, "output": 1_000_000}),
                         base_url="http://localhost:11434")  # $1 a token: the first response spends the budget
    model = scripted({"echo_say": {"text": "a"}}, "done")
    task = CueTask(instructions="i", skills={}, prompt="p", stage=MemoryStage(), models=[dear],
                   mcp_servers=[echo("5.00")], budget=Decimal("0.50"))
    result = asyncio.run(run_cue(task, build=lambda rm: model))
    tokens = result.input_tokens + result.output_tokens
    assert result.over_budget and result.brought_calls == 0 and result.cost == Decimal(tokens)  # the model's alone
