"""Read a role's mcp.json and resolve every ${NAME} from the actor's credentials, then the environment (D20).

Pydantic AI's own loader only reads the environment, so Zanni resolves the values and hands the engine
finished server specs: two actors on one machine get their own tokens without sharing a .env.
"""

import json
from collections.abc import Mapping
from pathlib import Path

from zanni.actor.contract import McpServerSpec
from zanni.actor.resolve import expand


def mcp_servers(role_folder: Path, credentials: Mapping[str, str], env: Mapping[str, str] | None = None) -> list[McpServerSpec]:
    path = role_folder / "mcp.json"
    if not path.is_file():
        return []
    servers = json.loads(path.read_text())["mcpServers"]  # its shape was checked with the role folder (D19)

    def x(value: str) -> str:
        return expand(value, credentials, env)

    specs = []
    for name, s in servers.items():
        specs.append(McpServerSpec(
            name=name,
            command=x(s["command"]) if s.get("command") else None,
            args=[x(a) for a in s.get("args") or []],
            env={k: x(v) for k, v in (s.get("env") or {}).items()},
            cwd=x(s["cwd"]) if s.get("cwd") else str(role_folder),
            url=x(s["url"]) if s.get("url") else None,
            headers={k: x(v) for k, v in (s.get("headers") or {}).items()},
        ))
    return specs
