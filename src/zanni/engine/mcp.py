"""Connect a role's MCP servers (D3), with ${NAME} already resolved by Zanni from the actor's credentials (D20)."""

from pydantic_ai.toolsets import AbstractToolset

from zanni.actor.contract import McpServerSpec


def mcp_toolsets(servers: list[McpServerSpec]) -> list[AbstractToolset]:
    return []  # item 6 connects them
