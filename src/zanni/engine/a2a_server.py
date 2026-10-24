"""The director's A2A server (D21): its card, one task per seat, and the token on every call (D24, D31).

The engine only carries messages. Every decision (who is cast, the next cue, when a seat ends) is the director's,
through the `Casting` interface (src/zanni/director/contract.py).
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

import uvicorn
from a2a.server.agent_execution import AgentExecutor
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.routes.common import DefaultServerCallContextBuilder
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, CancelTaskRequest, Task, TaskStatus, TaskStatusUpdateEvent
from a2a.utils.errors import ExtensionSupportRequiredError, InvalidParamsError, InvalidRequestError, UnsupportedOperationError
from google.protobuf.json_format import ParseDict
from starlette.applications import Starlette
from starlette.routing import BaseRoute

from zanni.director.contract import Casting, DirectorInfo, Outgoing
from zanni.engine.a2a_wire import STATES, BadMessage, from_a2a, join_problem, to_a2a
from zanni.protocol.card import EXTENSION_URI, DirectorCardParams
from zanni.protocol.messages import Join, Refused, Released, Report, Verdict

logging.getLogger("a2a").setLevel(logging.WARNING)


def director_card(info: DirectorInfo, url: str) -> AgentCard:
    """The director's Agent Card: A2A's own fields, plus the casting extension's params (casting-extension.md)."""
    params = DirectorCardParams(play=info.play, script=info.script).model_dump(mode="json")
    return ParseDict({
        "name": info.name, "description": info.description, "version": info.version,
        "supportedInterfaces": [{"url": url, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
        "capabilities": {"streaming": True, "pushNotifications": False,
                         "extensions": [{"uri": EXTENSION_URI, "required": True, "params": params,
                                         "description": "Zanni casting: join, cues, reports, release"}]},
        "securitySchemes": {"bearer": {"httpAuthSecurityScheme": {
            "scheme": "bearer", "description": "The play's join token, then the seat's token (D24)"}}},
        "securityRequirements": [{"schemes": {"bearer": {"list": []}}}],
        "defaultInputModes": ["application/json"], "defaultOutputModes": ["application/json"],
        "skills": [{"id": "join", "name": "Join", "tags": ["casting"],
                    "description": "Join this play: send zanni.join with your Agent Card, and the join token."}],
    }, AgentCard())


def bearer(context: ServerCallContext) -> str | None:
    value = context.state.get("headers", {}).get("authorization", "")
    scheme, _, token = value.partition(" ")
    return token.strip() or None if scheme.lower() == "bearer" else None


def peer(context: ServerCallContext) -> str | None:
    return context.state.get("peer")


class _WithPeer(DefaultServerCallContextBuilder):
    """A2A's default context, plus the address the request came from: an actor's host (max_seats_per_host)."""

    def build(self, request):
        context = super().build(request)
        context.state["peer"] = request.client.host if request.client else None
        return context


def reached_at(context: ServerCallContext) -> str:
    headers = context.state.get("headers", {})
    scheme = headers.get("x-forwarded-proto", "http")
    return f"{scheme}://{headers.get('host', '127.0.0.1')}"


async def publish(queue, task_id: str, context_id: str, out: Outgoing) -> None:
    message = to_a2a(out.message, task_id=task_id, context_id=context_id) if out.message else None
    status = TaskStatus(state=STATES[out.state], message=message) if message else TaskStatus(state=STATES[out.state])
    await queue.enqueue_event(TaskStatusUpdateEvent(task_id=task_id, context_id=context_id, status=status))


class SeatExecutor(AgentExecutor):
    """Turns each message on a seat's task into a call to the director, and its answer into the task's status."""

    def __init__(self, casting: Casting):
        self.casting = casting

    async def execute(self, context, event_queue) -> None:
        task_id, context_id = context.task_id, context.context_id
        if context.current_task is None:  # a new task: only a join starts one (the handler checked)
            problem = join_problem(context.message)
            join = None if problem else from_a2a(context.message, "zanni.join")
            answer = await self.casting.join(bearer(context.call_context), task_id, join, problem,
                                             reached_at(context.call_context), peer(context.call_context))
            state = "rejected" if isinstance(answer, Refused) else "working"
            await event_queue.enqueue_event(Task(id=task_id, context_id=context_id, status=TaskStatus(
                state=STATES[state], message=to_a2a(answer, task_id=task_id, context_id=context_id))))
            if state == "rejected":
                return
        else:
            message = from_a2a(context.message, "zanni.report", "zanni.released", "zanni.verdict")
            if isinstance(message, Released):
                await self.casting.released(task_id, message)
                await publish(event_queue, task_id, context_id, Outgoing("completed"))
                return
            if isinstance(message, Verdict):
                await self.casting.verdict(task_id, message)
            else:
                assert isinstance(message, Report)
                await self.casting.report(task_id, message)
            await publish(event_queue, task_id, context_id, Outgoing("working"))
        out = await self.casting.next_for(task_id)
        await publish(event_queue, task_id, context_id, out)

    async def cancel(self, context, event_queue) -> None:
        """Only the director ends a task this way (an actor can't cancel), with the status it chose."""
        await publish(event_queue, context.task_id, context.context_id or "", self.casting.ending(context.task_id))


class SeatHandler(DefaultRequestHandler):
    """A2A's default handler, with Zanni's rules on every call: the extension, the seat token, contact (D31)."""

    def __init__(self, casting: Casting, card: AgentCard):
        super().__init__(agent_executor=SeatExecutor(casting), task_store=InMemoryTaskStore(), agent_card=card)
        self.casting = casting

    def _extension(self, context: ServerCallContext) -> None:
        if EXTENSION_URI not in context.requested_extensions:
            raise ExtensionSupportRequiredError(message=f"send the A2A-Extensions header with {EXTENSION_URI}")

    def _seat(self, task_id: str, context: ServerCallContext) -> None:
        self._extension(context)
        problem = self.casting.authorise(bearer(context), task_id)
        if problem:
            raise InvalidRequestError(message=f"not-authorised: {problem}")
        self.casting.contact(task_id)

    def _message(self, params) -> None:
        if params.message.task_id:
            kinds = ("zanni.report", "zanni.released", "zanni.verdict")
        else:
            kinds = ("zanni.join",)
            if params.message.context_id:
                raise InvalidParamsError(message="a join starts a new task; send it without a task or context id")
        try:
            from_a2a(params.message, *kinds)
        except BadMessage as e:
            if kinds != ("zanni.join",):
                raise InvalidParamsError(message=str(e)) from None
            # A broken join still gets an answer: a task rejected with `bad-card` (casting-extension.md).

    async def on_message_send(self, params, context):
        if params.message.task_id:
            self._seat(params.message.task_id, context)
        else:
            self._extension(context)
        self._message(params)
        return await super().on_message_send(params, context)

    async def on_message_send_stream(self, params, context):
        if params.message.task_id:
            self._seat(params.message.task_id, context)
        else:
            self._extension(context)
        self._message(params)
        async for event in super().on_message_send_stream(params, context):
            yield event

    async def on_get_task(self, params, context):
        self._seat(params.id, context)
        return await super().on_get_task(params, context)

    async def on_subscribe_to_task(self, params, context):
        self._seat(params.id, context)
        self.casting.contact(params.id, streaming=True)
        try:
            async for event in super().on_subscribe_to_task(params, context):
                self.casting.contact(params.id)
                yield event
        finally:
            self.casting.contact(params.id, streaming=False)

    async def on_list_tasks(self, params, context):
        raise UnsupportedOperationError(message="listing tasks would show other seats' tasks")

    async def on_cancel_task(self, params, context):
        raise UnsupportedOperationError(message="only the director ends a seat; answer zanni.release instead")

    async def end(self, task_id: str) -> None:
        """The director ends a seat's task itself, with the status `Casting.ending` gives (D21)."""
        with contextlib.suppress(Exception):  # already ended: nothing to do
            await super().on_cancel_task(CancelTaskRequest(id=task_id), ServerCallContext())


def director_app(casting: Casting, info: DirectorInfo, url: str,
                 mounts: list[BaseRoute] = (), lifespans=()) -> tuple[Starlette, SeatHandler]:
    """The director's HTTP app: its card at A2A's well-known path, JSON-RPC at `/`, and any extra mounts."""
    card = director_card(info, url)
    handler = SeatHandler(casting, card)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with contextlib.AsyncExitStack() as stack:
            for enter in lifespans:
                await stack.enter_async_context(enter())
            try:
                yield
            finally:
                await handler.aclose()

    routes = [*create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/", context_builder=_WithPeer()),
              *mounts]
    return Starlette(routes=routes, lifespan=lifespan), handler


async def _drain(server: uvicorn.Server, seconds: float) -> None:
    """Give requests still in flight (a stream ending, a last reply) a moment to finish before shutting down."""
    loop = asyncio.get_running_loop()
    until = loop.time() + seconds
    while server.server_state.tasks and loop.time() < until:
        await asyncio.sleep(0.02)


class Listening:
    """A running uvicorn server, on the address it actually bound (port 0 picks a free one)."""

    def __init__(self, server: uvicorn.Server, task: asyncio.Task, host: str, port: int):
        self.server, self.task, self.host, self.port = server, task, host, port

    @property
    def url(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}"


@contextlib.asynccontextmanager
async def listening(app_for_url, host: str = "127.0.0.1", port: int = 0,
                    drain_for: float = 2.0) -> AsyncIterator[Listening]:
    """Bind first, then build the app for the bound URL (the card must name it), then serve until the block ends."""
    import socket

    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    bound = sock.getsockname()[1]
    public = "127.0.0.1" if host in ("0.0.0.0", "") else ("::1" if host == "::" else host)
    app = app_for_url(Listening(None, None, public, bound).url)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False, lifespan="on"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        if task.done():
            task.result()  # surface a failure to start
        await asyncio.sleep(0.02)
    try:
        yield Listening(server, task, public, bound)
    finally:
        await _drain(server, drain_for)
        server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError):
            await task
        sock.close()
