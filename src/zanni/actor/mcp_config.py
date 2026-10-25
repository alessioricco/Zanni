"""Read a role's mcp.json and the tools the actor brings, and resolve every ${NAME} from the actor's credentials,
then the environment (D20, D53).

Pydantic AI's own loader only reads the environment, so Zanni resolves the values and hands the engine
finished server specs: two actors on one machine get their own tokens without sharing a .env.
"""

import json
import os
from collections.abc import Mapping
from pathlib import Path

from zanni.actor.contract import McpServerSpec
from zanni.actor.resolve import Unresolved, expand
from zanni.files.schemas import ToolBinding

WORKSPACE_VAR = "ZANNI_WORKSPACE"  # the folder of the seat's workspace, for a tool the actor brings (D52)


def mcp_servers(role_folder: Path, credentials: Mapping[str, str], env: Mapping[str, str] | None = None, *,
                bindings: Mapping[str, ToolBinding] | None = None, needs: list[str] | None = None,
                workspace: Path | None = None) -> list[McpServerSpec]:
    """The role's servers, each replaced by the actor's own when its configuration binds that tool (D53).

    `needs` is the role's `needs.tools`: a binding for any other name is refused, so an actor can't add a tool its
    role didn't ask for. `workspace`, when the actor has one, is what `${ZANNI_WORKSPACE}` names.
    """
    bindings = bindings or {}
    if needs is not None and (extra := [name for name in bindings if name not in needs]):
        raise Unresolved(f"the actor configuration's `tools` binds {', '.join(extra)}, which the role doesn't need; "
                         f"bind only tools in its needs.tools: {', '.join(needs) or 'none'}")
    env = dict(os.environ if env is None else env)
    if workspace is not None:
        env[WORKSPACE_VAR] = str(workspace)

    def x(value: str) -> str:
        return expand(value, credentials, env)

    path = role_folder / "mcp.json"
    servers = json.loads(path.read_text())["mcpServers"] if path.is_file() else {}  # its shape was checked (D19)
    specs = []
    for name, s in servers.items():
        if name in bindings:
            continue
        specs.append(McpServerSpec(
            name=name,
            command=x(s["command"]) if s.get("command") else None,
            args=[x(a) for a in s.get("args") or []],
            env={k: x(v) for k, v in (s.get("env") or {}).items()},
            cwd=x(s["cwd"]) if s.get("cwd") else str(role_folder),
            url=x(s["url"]) if s.get("url") else None,
            headers={k: x(v) for k, v in (s.get("headers") or {}).items()},
        ))
    for name, b in bindings.items():
        specs.append(McpServerSpec(
            name=name,
            command=x(b.command) if b.command else None,
            args=[x(a) for a in b.args],
            env={k: x(v) for k, v in b.env.items()},
            cwd=str(workspace) if workspace is not None and b.command else None,
            url=x(b.url) if b.url else None,
            headers={k: x(v) for k, v in b.headers.items()},
            brought=True,
            price=b.price.per_call if b.price else None,
        ))
    return specs
