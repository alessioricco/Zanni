"""The `mcp` stage backend (D47): any MCP server offering the five stage tools, reached with the director's token.

Storage only (D43): the director's layer enforces each seat's permissions above it. `author` and `note` go to the
server as optional arguments; a server that doesn't take them still works. An operation that gets `unavailable` is
retried briefly, reconnecting; if the server stays away, `down` says why, and the director pauses the play.
"""

from __future__ import annotations  # `list` is a method name below; Python < 3.14 evaluates annotations eagerly

import asyncio
import contextlib
from pathlib import Path

from zanni.engine.stage_mcp import RemoteStage, remote_stage
from zanni.stage.errors import StageError

RETRIES = (0.5, 1.0, 2.0)  # seconds between attempts, before the server counts as down


class McpBackend:
    kind = "mcp"

    def __init__(self, url: str, token: str, retries: tuple[float, ...] = RETRIES):
        self.url, self._token, self.retries = url, token, retries
        self._remote: RemoteStage | None = None
        self._owner: tuple[asyncio.Task, asyncio.Event] | None = None
        self.labels = True  # whether the server takes `author` and `note`
        self.down: str | None = None  # why the server is unreachable, once retries ran out

    async def open(self) -> None:
        """Connect, and check the token with one call: a wrong token or no server fails here, before the play."""
        await self._connect()
        await self._remote.changes()

    async def _connect(self) -> None:
        """One background task owns each connection: an MCP client must be closed by the task that opened it, and
        any seat's request may be the one that reconnects."""
        await self._disconnect()
        ready: asyncio.Future = asyncio.get_running_loop().create_future()
        stop = asyncio.Event()

        async def own():
            try:
                async with remote_stage(self.url, self._token) as remote:
                    ready.set_result(remote)
                    await stop.wait()
            except BaseException as e:  # a broken connection ends here; the next call reconnects
                if not ready.done():
                    ready.set_exception(e)

        self._owner = (asyncio.create_task(own()), stop)
        self._remote = await ready

    async def _disconnect(self) -> None:
        owner, self._owner, self._remote = self._owner, None, None
        if owner is not None:
            owner[1].set()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(owner[0], 5)

    async def _call(self, tool: str, **args):
        last = None
        for wait in (0, *self.retries):
            if wait:
                await asyncio.sleep(wait)
            try:
                if self._remote is None:
                    await self._connect()
                value = await self._remote._call(tool, **args)
                self.down = None
                return value
            except StageError as e:
                if e.code != "unavailable":
                    raise
                last = e
                await self._disconnect()  # the next attempt reconnects: the server may have restarted
        self.down = f"the stage's server at {self.url} isn't answering: {last}"
        raise StageError("unavailable", self.down)

    async def read(self, path: str) -> str:
        return await self._call("stage_read", path=path)

    async def write(self, path: str, content: str, *, author: str | None = None, note: str | None = None) -> str:
        return await self._labelled("stage_write", path=path, content=content, author=author, note=note)

    async def delete(self, path: str, *, author: str | None = None, note: str | None = None) -> str:
        return await self._labelled("stage_delete", path=path, author=author, note=note)

    async def _labelled(self, tool: str, **args) -> str:
        """With `author` and `note`, unless the server has shown it doesn't take them (D47)."""
        if not self.labels:
            args = {k: v for k, v in args.items() if k not in ("author", "note")}
        try:
            return await self._call(tool, **args)
        except StageError as e:
            if not self.labels or not any(w in str(e).lower() for w in ("author", "unexpected", "extra")):
                raise
            self.labels = False
            return await self._labelled(tool, **args)

    async def list(self, folder: str = "") -> list[str]:
        return await self._call("stage_list", path=folder)

    async def changes(self, since: str | None = None) -> tuple[list[tuple[str, str]], str]:
        value = await self._call("stage_changes", since=since)
        return [(c["path"], c["change"]) for c in value["changes"]], value["marker"]

    async def snapshot(self, into: Path) -> str:
        """Every file, listed and read into `into`; files that aren't text are left out."""
        marker = (await self.changes())[1]
        for path in await self.list(""):
            try:
                text = await self.read(path)
            except StageError as e:
                if e.code != "not-text":
                    raise
                continue
            target = into / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        return marker

    async def close(self) -> None:
        await self._disconnect()
