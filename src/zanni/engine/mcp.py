"""Connect a role's MCP servers (D3), with ${NAME} already resolved by Zanni from the actor's credentials (D20)."""

from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import AbstractToolset

from zanni.actor.contract import McpServerSpec

# A tool's refusal (a command not allowed, a path outside the workspace) is feedback for the model. It may fail this
# many times in a row before the cue ends; a success resets the count.
TOOL_RETRIES = 3
# Seconds a tool server has to start and answer MCP's handshake: a server started with Python, such as
# zanni:workspace, can take several seconds on a busy machine (found by the suite, under load).
TOOL_START = 30
# Seconds the actor waits for one tool call: longer than zanni:workspace's own limit on a command (600 s), so the
# workspace stops a slow command and says so, rather than the call being abandoned with the command still running.
TOOL_CALL = 15 * 60


def mcp_toolsets(servers: list[McpServerSpec]) -> list[AbstractToolset]:
    """One toolset per server, its tools prefixed with the server's name, as Pydantic AI's own loader does."""
    toolsets: list[AbstractToolset] = []
    for s in servers:
        if s.command:
            client = StdioTransport(command=s.command, args=list(s.args), env=dict(s.env) or None, cwd=s.cwd)
            toolset = MCPToolset(client, id=s.name, max_retries=TOOL_RETRIES, init_timeout=TOOL_START,
                                 read_timeout=TOOL_CALL)
        else:
            toolset = MCPToolset(s.url, id=s.name, headers=dict(s.headers) or None, max_retries=TOOL_RETRIES,
                                 init_timeout=TOOL_START, read_timeout=TOOL_CALL)
        toolsets.append(toolset.prefixed(s.name))
    return toolsets
