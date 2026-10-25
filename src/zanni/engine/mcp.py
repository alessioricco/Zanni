"""Connect a role's MCP servers (D3), with ${NAME} already resolved by Zanni from the actor's credentials (D20)."""

from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import AbstractToolset

from zanni.actor.contract import McpServerSpec

# A tool's refusal (a command not allowed, a path outside the workspace) is feedback for the model. It may fail this
# many times in a row before the cue ends; a success resets the count.
TOOL_RETRIES = 3


def mcp_toolsets(servers: list[McpServerSpec]) -> list[AbstractToolset]:
    """One toolset per server, its tools prefixed with the server's name, as Pydantic AI's own loader does."""
    toolsets: list[AbstractToolset] = []
    for s in servers:
        if s.command:
            client = StdioTransport(command=s.command, args=list(s.args), env=dict(s.env) or None, cwd=s.cwd)
            toolset = MCPToolset(client, id=s.name, max_retries=TOOL_RETRIES)
        else:
            toolset = MCPToolset(s.url, id=s.name, headers=dict(s.headers) or None, max_retries=TOOL_RETRIES)
        toolsets.append(toolset.prefixed(s.name))
    return toolsets
