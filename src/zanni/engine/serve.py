"""Serve a director: its A2A server and its stage's MCP server on one address, and its heartbeat watch (D29)."""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from zanni.director.casting import Director
from zanni.director.contract import DirectorInfo
from zanni.engine.a2a_server import Listening, director_app, listening
from zanni.engine.stage_mcp import stage_server


@contextlib.asynccontextmanager
async def serving(director: Director, info: DirectorInfo, host: str = "127.0.0.1",
                  port: int = 0) -> AsyncIterator[Listening]:
    handlers = []

    def app_for(url: str):
        mount, lifespan = stage_server(director, host)
        app, handler = director_app(director, info, url, mounts=[mount], lifespans=[lifespan])
        handlers.append(handler)
        return app

    async with listening(app_for, host, port) as server:
        director.end_task = handlers[0].end
        watcher = asyncio.create_task(director.watch())
        try:
            yield server
        finally:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
            # End every task's event queue before the server stops, so an actor's open task stream finishes
            # cleanly instead of being cut by the shutdown (`listening` then waits for it).
            await handlers[0].aclose()
