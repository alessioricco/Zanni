"""Serve a director: its A2A server and its stage's MCP server on one address, and its heartbeat watch (D29)."""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from zanni.director.casting import Director
from zanni.director.contract import DirectorInfo
from zanni.engine.a2a_server import Listening, director_app, listening
from zanni.engine.stage_mcp import stage_server

OWNER_PATH = "/zanni/owner"


def owner_route(owner) -> Route:
    """The owner's endpoint beside A2A (D38): GET the play's state, POST a decision, with the owner token."""

    async def endpoint(request: Request) -> JSONResponse:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        problem = owner.authorise(token.strip() if scheme.lower() == "bearer" else None)
        if problem:
            return JSONResponse({"error": problem}, status_code=401)
        if request.method == "GET":
            return JSONResponse(owner.status())
        try:
            body = json.loads(await request.body() or b"{}")
            action, note = str(body.get("action", "")), str(body.get("note") or "")
            another_round = body.get("another_round", False) is True  # D60
        except (ValueError, AttributeError):
            return JSONResponse({"error": 'send JSON such as {"action": "approve", "note": "…"}'}, status_code=400)
        status, answer = owner.decide(action, note, another_round=another_round)
        return JSONResponse(answer, status_code=status)

    return Route(OWNER_PATH, endpoint, methods=["GET", "POST"])


@contextlib.asynccontextmanager
async def serving(director: Director, info: DirectorInfo, host: str = "127.0.0.1",
                  port: int = 0, owner=None) -> AsyncIterator[Listening]:
    handlers = []

    def app_for(url: str):
        mount, lifespan = stage_server(director, host)
        routes = [owner_route(owner), mount] if owner is not None else [mount]
        app, handler = director_app(director, info, url, mounts=routes, lifespans=[lifespan])
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
