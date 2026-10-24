"""Serve folder stages over the director's MCP server on loopback, and reach them through RemoteStage.

`served({token: stage})` runs the server and the clients on a background event loop, and gives each stage back
as a plain object with the local stage's synchronous methods, so the same tests run against both.
"""

import asyncio
import contextlib
import threading

from starlette.applications import Starlette

from zanni.engine.a2a_server import listening
from zanni.engine.stage_mcp import remote_stage, stage_server


class Tokens:
    def __init__(self, stages):
        self.stages, self.revoked = dict(stages), set()

    def stage_for(self, token):
        return None if token in self.revoked else self.stages.get(token)


class Synchronous:
    def __init__(self, remote, loop, root):
        self.remote, self.loop, self.root = remote, loop, root

    def __getattr__(self, name):
        method = getattr(self.remote, name)
        return lambda *args: asyncio.run_coroutine_threadsafe(method(*args), self.loop).result(30)


class Local:
    """A seat's view on the director's side, called synchronously, so the same tests run on both sides."""

    def __init__(self, seat):
        self.seat, self.root = seat, seat.stage.backend.root

    def __getattr__(self, name):
        method = getattr(self.seat, name)
        return lambda *args: asyncio.run(method(*args))


@contextlib.contextmanager
def served(stages: dict, tokens: Tokens | None = None):
    tokens = tokens or Tokens(stages)
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    ready, stop = loop.create_future(), asyncio.Event()

    async def main():
        def app_for(url):
            mount, lifespan = stage_server(tokens, "127.0.0.1")
            return Starlette(routes=[mount], lifespan=lambda app: lifespan())

        async with listening(app_for) as server, contextlib.AsyncExitStack() as stack:
            remotes = {t: await stack.enter_async_context(remote_stage(f"{server.url}/stage/mcp", t)) for t in stages}
            ready.set_result((server.url, remotes))
            await stop.wait()

    running = asyncio.run_coroutine_threadsafe(main(), loop)
    url, remotes = asyncio.run_coroutine_threadsafe(asyncio.wait_for(asyncio.shield(ready), 30), loop).result(30)
    try:
        yield {t: Synchronous(r, loop, stages[t].stage.backend.root) for t, r in remotes.items()} | {"url": url, "tokens": tokens}
    finally:
        loop.call_soon_threadsafe(stop.set)
        running.result(30)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)
