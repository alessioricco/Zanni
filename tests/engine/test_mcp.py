"""D3, D20: a role's MCP server, started over stdio, with ${NAME} resolved from the actor's credentials."""

import asyncio
import json
import sys
from pathlib import Path

from tests.engine.fakes import MemoryStage, entry, scripted
from zanni.actor.contract import CueTask
from zanni.actor.mcp_config import mcp_servers
from zanni.engine.run import run_cue

ECHO = Path(__file__).with_name("echo_mcp.py")


def test_a_role_server_gets_its_value_from_the_actors_credentials(tmp_path):
    (tmp_path / "mcp.json").write_text(json.dumps({"mcpServers": {"echo": {
        "command": sys.executable, "args": [str(ECHO)], "env": {"GREETING": "${GREETING}"}}}}))
    servers = mcp_servers(tmp_path, {"GREETING": "hello-from-credentials"}, env={})
    assert servers[0].env == {"GREETING": "hello-from-credentials"}

    model = scripted({"echo_say": {"text": "zanni"}}, "done")
    task = CueTask(instructions="i", skills={}, prompt="p", stage=MemoryStage(), models=[entry()], mcp_servers=servers)
    result = asyncio.run(run_cue(task, build=lambda rm: model))
    assert result.tool_calls == ["echo_say"]
    returned = [p.content for m in model.seen for p in m.parts if p.part_kind == "tool-return"]
    assert returned == ["hello-from-credentials: zanni"]
