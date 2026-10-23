"""Connect a role's MCP servers (D3), with ${NAME} already resolved by Zanni from the actor's credentials (D20)."""

from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import AbstractToolset

from zanni.actor.contract import McpServerSpec


def mcp_toolsets(servers: list[McpServerSpec]) -> list[AbstractToolset]:
    """One toolset per server, its tools prefixed with the server's name, as Pydantic AI's own loader does."""
    toolsets: list[AbstractToolset] = []
    for s in servers:
        if s.command:
            client = StdioTransport(command=s.command, args=list(s.args), env=dict(s.env) or None, cwd=s.cwd)
            toolset = MCPToolset(client, id=s.name)
        else:
            toolset = MCPToolset(s.url, id=s.name, headers=dict(s.headers) or None)
        toolsets.append(toolset.prefixed(s.name))
    return toolsets
