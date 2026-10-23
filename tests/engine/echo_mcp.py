"""A tiny MCP server for tests, on the official mcp SDK: one tool that echoes, and reports one env value."""

import os

from mcp.server.mcpserver import MCPServer

server = MCPServer("echo")


@server.tool()
def say(text: str) -> str:
    """Echo the text back, with the GREETING environment value."""
    return f"{os.environ.get('GREETING', '?')}: {text}"


if __name__ == "__main__":
    server.run("stdio")
