"""Read a role's mcp.json and the tools the actor brings, and resolve every ${NAME} from the actor's credentials,
then the environment (D20, D53).

Pydantic AI's own loader only reads the environment, so Zanni resolves the values and hands the engine
finished server specs: two actors on one machine get their own tokens without sharing a .env.
"""

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from zanni.actor.contract import McpServerSpec
from zanni.actor.resolve import Unresolved, expand
from zanni.files.schemas import WORKSPACE_SERVER, ToolBinding
from zanni.files.validation import is_secret_name

WORKSPACE_VAR = "ZANNI_WORKSPACE"  # the folder of the seat's workspace, for a tool the actor brings (D52)


def uses_workspace(role_folder: Path) -> bool:
    """Whether the role's mcp.json names the built-in `zanni:workspace` (D52)."""
    path = role_folder / "mcp.json"
    servers = json.loads(path.read_text())["mcpServers"] if path.is_file() else {}
    return any(s.get("command") == WORKSPACE_SERVER for s in servers.values())


def workspace_server(name: str, workspace: Path | None, commands: list[str], env: Mapping[str, str]) -> McpServerSpec:
    """The built-in workspace server, as a process: it may run only the configuration's `workspace.commands`, and
    its environment holds nothing that looks like a secret, so a command it runs can't read the actor's keys."""
    if workspace is None:
        raise Unresolved(f"the role's {name} server is {WORKSPACE_SERVER}, which needs a workspace, and this actor "
                         "has none here")
    args = ["-m", "zanni.engine.workspace_server", "--folder", str(workspace)]
    for command in commands:
        args += ["--command", command]
    return McpServerSpec(name=name, command=sys.executable, args=args, cwd=str(workspace),
                         env={k: v for k, v in env.items() if not is_secret_name(k)})


def mcp_servers(role_folder: Path, credentials: Mapping[str, str], env: Mapping[str, str] | None = None, *,
                bindings: Mapping[str, ToolBinding] | None = None, needs: list[str] | None = None,
                workspace: Path | None = None, commands: list[str] = ()) -> list[McpServerSpec]:
    """The role's servers, each replaced by the actor's own when its configuration binds that tool (D53).

    `needs` is the role's `needs.tools`: a binding for any other name is refused, so an actor can't add a tool its
    role didn't ask for. `workspace`, when the actor has one, is what `${ZANNI_WORKSPACE}` names, and where
    `zanni:workspace` runs `commands`, the configuration's `workspace.commands` (D52).
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
        if s.get("command") == WORKSPACE_SERVER:
            specs.append(workspace_server(name, workspace, list(commands), {k: v for k, v in env.items()
                                                                          if k != WORKSPACE_VAR}))
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
