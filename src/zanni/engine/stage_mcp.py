"""The stage over MCP (D16, D31): the director serves it, on the official `mcp` SDK; the actor reaches it.

Server: Streamable HTTP, one bearer token per seat, the five stage operations as tools, refused operations as
tool errors with the text `<code>: <message>`. Client: turns those back into the same StageError the local
stage raises, so a model sees the same tools and the same errors on a local or a remote stage.
"""

from __future__ import annotations  # a `list` method shadows `list` in the class body; Python < 3.14 evaluates eagerly

import contextlib
import json
import logging
import re
from collections.abc import AsyncIterator

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Mount

from zanni.actor.contract import Stage, StageError
from zanni.director.contract import Casting

STAGE_TOOLS = ("stage_read", "stage_write", "stage_list", "stage_delete", "stage_changes")
# A refused operation's text ends with `<code>: <message>`; the MCP SDK puts its own prefix before it.
STAGE_ERROR = re.compile(r"\b(invalid-path|not-permitted|not-found|not-text|unknown-marker|unavailable|not-authorised): (.*)",
                         re.DOTALL)
logging.getLogger("httpx2").setLevel(logging.WARNING)


class _SeatTokens:
    """Bearer tokens are the seats' stage tokens; the director says which are valid, on every request."""

    def __init__(self, casting: Casting):
        self.casting = casting

    async def verify_token(self, token: str) -> AccessToken | None:
        return AccessToken(token=token, client_id="seat", scopes=[]) if self.casting.stage_for(token) else None


def stage_server(casting: Casting, host: str) -> tuple[Mount, object]:
    """The stage's MCP server, to mount at `/stage` (so it answers at `/stage/mcp`), and its lifespan."""
    server = MCPServer("zanni-stage", instructions="The play's stage: read and write files within your seat's "
                       "permissions.", token_verifier=_SeatTokens(casting), log_level="WARNING",
                       auth=AuthSettings(issuer_url="http://127.0.0.1", resource_server_url=None))

    def seat_stage() -> Stage:
        token = get_access_token()
        stage = casting.stage_for(token.token) if token else None
        if stage is None:  # revoked since the request was authenticated
            raise ToolError("not-authorised: this seat's stage token is no longer valid")
        return stage

    async def run(operation):
        try:
            return await operation(seat_stage())
        except StageError as e:
            raise ToolError(f"{e.code}: {e}") from None

    @server.tool()
    async def stage_read(path: str) -> str:
        """Read a file from the stage. Paths are relative to the stage root, e.g. backlog/round-1.md."""
        return await run(lambda s: s.read(path))

    @server.tool()
    async def stage_write(path: str, content: str) -> str:
        """Write a whole file to the stage, replacing it if it exists. Returns the new change marker."""
        return await run(lambda s: s.write(path, content))

    @server.tool()
    async def stage_list(path: str = "") -> list[str]:
        """List the files under a stage folder that you may read; empty for the root."""
        return await run(lambda s: s.list(path))

    @server.tool()
    async def stage_delete(path: str) -> str:
        """Delete a file from the stage. Returns the new change marker."""
        return await run(lambda s: s.delete(path))

    @server.tool()
    async def stage_changes(since: str | None = None) -> dict:
        """What changed on the stage since a change marker (or since the start), and the current marker."""
        changes, marker = await run(lambda s: s.changes(since))
        return {"changes": [{"path": p, "change": c} for p, c in changes], "marker": marker}

    # DNS-rebinding protection only makes sense on loopback, where the SDK turns it on; a director listening on
    # the network is reached by whatever address the actor uses, and the seat token is what protects it.
    security = None if host in ("127.0.0.1", "localhost", "::1") else TransportSecuritySettings(
        enable_dns_rebinding_protection=False)
    app = server.streamable_http_app(stateless_http=True, json_response=True, host=host, transport_security=security)
    return Mount("/stage", app=app), lambda: app.router.lifespan_context(app)


class RemoteStage:
    """The Stage operations, over the director's MCP server, for one seat (async: each is a network call)."""

    def __init__(self, client: Client):
        self.client = client

    async def _call(self, tool: str, **args):
        try:
            result = await self.client.call_tool(tool, {k: v for k, v in args.items() if v is not None})
        except Exception as e:
            raise StageError("unavailable", f"the stage couldn't be reached: {type(e).__name__}: {e}"[:300]) from None
        text = "".join(getattr(c, "text", "") for c in result.content)
        if result.is_error:
            found = STAGE_ERROR.search(text)
            raise StageError(found[1], found[2]) if found else StageError("unavailable", text)
        if result.structured_content is not None:
            value = result.structured_content
            return value["result"] if set(value) == {"result"} else value
        return json.loads(text) if tool in ("stage_list", "stage_changes") else text

    async def read(self, path: str) -> str:
        return await self._call("stage_read", path=path)

    async def write(self, path: str, content: str) -> str:
        return await self._call("stage_write", path=path, content=content)

    async def list(self, path: str = "") -> list[str]:
        return await self._call("stage_list", path=path)

    async def delete(self, path: str) -> str:
        return await self._call("stage_delete", path=path)

    async def changes(self, since: str | None = None) -> tuple[list[tuple[str, str]], str]:
        value = await self._call("stage_changes", since=since)
        return [(c["path"], c["change"]) for c in value["changes"]], value["marker"]


@contextlib.asynccontextmanager
async def remote_stage(mcp_url: str, token: str) -> AsyncIterator[RemoteStage]:
    """Connect to a stage's MCP server with a seat's stage token, for the seat's whole life."""
    refused: list[int] = []

    async def note(response) -> None:  # the MCP client reports a refused token only as "an error response"
        if response.status_code in (401, 403):
            refused.append(response.status_code)

    async with contextlib.AsyncExitStack() as stack:
        http = await stack.enter_async_context(httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}, timeout=httpx2.Timeout(30.0, read=300.0),
            event_hooks={"response": [note]}))
        try:
            client = await stack.enter_async_context(Client(streamable_http_client(mcp_url, http_client=http)))
        except Exception as e:  # only connecting is translated; errors in the caller's own block pass through
            why = f"the server refused the token (HTTP {refused[0]})" if refused else _first(e)
            raise StageError("unavailable", f"couldn't connect to the stage at {mcp_url}: {why}") from None
        yield RemoteStage(client)


def _first(e: BaseException) -> str:
    """The first real error inside an exception group (anyio's task groups wrap them)."""
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    return f"{type(e).__name__}: {e}"[:300]
