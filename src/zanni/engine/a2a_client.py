"""The actor's A2A client (D21): fetch the director's card, join, follow the seat's task, send reports.

The actor is always the client and never listens. It follows its task with SubscribeToTask, and falls back to
GetTask polling when the stream drops; each call is contact, so the director knows the seat is alive (D31).
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from a2a.client import A2ACardResolver, ClientCallContext, ClientConfig, ClientFactory
from a2a.types import AgentCard, GetTaskRequest, SendMessageConfiguration, SendMessageRequest, SubscribeToTaskRequest
from google.protobuf.json_format import MessageToDict

from zanni.engine.a2a_wire import EXTENSIONS_HEADER, STATE_NAMES, BadMessage, from_a2a, to_a2a
from zanni.protocol.card import EXTENSION_URI
from zanni.protocol.encoding import Wire
from zanni.protocol.messages import Cast, Join, Refused

TERMINAL = ("completed", "canceled", "rejected", "failed")


class DirectorError(Exception):
    """The director couldn't be reached, or answered in a way the casting extension doesn't allow."""


class NotAuthorised(DirectorError):
    """The director refused the seat's token: it expired, or the seat was released."""


@dataclass(frozen=True)
class Status:
    """One observed state of the seat's task, and the casting message it carries, if any."""

    state: str
    message: Wire | None


def _context(token: str | None) -> ClientCallContext:
    params = {EXTENSIONS_HEADER: EXTENSION_URI}
    if token:
        params["Authorization"] = f"Bearer {token}"
    return ClientCallContext(service_parameters=params)


def _status(task_or_event) -> Status:
    status = task_or_event.status
    state = STATE_NAMES.get(status.state, "failed")
    message = None
    if status.HasField("message"):
        try:
            message = from_a2a(status.message)
        except BadMessage as e:
            raise DirectorError(f"the director sent a message that isn't valid: {e}") from None
    return Status(state, message)


def _call_error(e: Exception) -> DirectorError:
    text = str(e)
    if "not-authorised" in text:
        return NotAuthorised(text[text.index("not-authorised"):])
    return DirectorError(f"{type(e).__name__}: {text}"[:300])


class DirectorClient:
    """One actor's connection to one director, at the URL it was given."""

    def __init__(self, url: str, *, connect_timeout: float = 10.0):
        self.url = url.rstrip("/")
        # No read timeout: a stream stays open while the actor works (the spike's 5 s default broke long cues).
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(connect_timeout, read=None))
        self.card: AgentCard | None = None
        self._send = self._stream = None
        self._contexts: dict[str, str] = {}  # task id -> its context id, which every later message must carry

    async def close(self) -> None:
        await self.http.aclose()

    async def fetch_card(self) -> dict:
        """The director's card, in A2A's JSON form. Its calls go to the URL the actor was given, not the card's
        own address, which may name an interface only the director's machine can reach."""
        try:
            card = await A2ACardResolver(self.http, self.url).get_agent_card()
        except Exception as e:
            raise DirectorError(f"couldn't fetch the director's card from {self.url}: {e}") from None
        del card.supported_interfaces[:]
        card.supported_interfaces.add(url=self.url, protocol_binding="JSONRPC", protocol_version="1.0")
        self.card = card
        self._send = ClientFactory(ClientConfig(httpx_client=self.http, streaming=False)).create(card)
        self._stream = ClientFactory(ClientConfig(httpx_client=self.http, streaming=True)).create(card)
        return MessageToDict(card)

    async def _send_message(self, message: Wire, token: str | None, task_id: str = ""):
        request = SendMessageRequest(message=to_a2a(message, task_id=task_id, role="ROLE_USER",
                                                    context_id=self._contexts.get(task_id, "")),
                                     configuration=SendMessageConfiguration(return_immediately=True))
        try:
            async for response in self._send.send_message(request, context=_context(token)):
                return response.task
        except Exception as e:
            raise _call_error(e) from None
        raise DirectorError("the director answered with no task")

    async def join(self, card: dict, token: str | None, part: str | None = None) -> tuple[str, Cast | Refused]:
        """Ask to join; the answer is the seat's task id, and the cast or the refusal (casting-extension.md)."""
        task = await self._send_message(Join(kind="zanni.join", card=card, part=part), token)
        self._contexts[task.id] = task.context_id
        status = _status(task)
        if not isinstance(status.message, (Cast, Refused)):
            raise DirectorError(f"the director answered a join with {status.state} and no cast or refusal")
        return task.id, status.message

    async def send(self, task_id: str, token: str, message: Wire) -> None:
        await self._send_message(message, token, task_id)

    async def poll(self, task_id: str, token: str) -> Status:
        try:
            task = await self._send.get_task(GetTaskRequest(id=task_id), context=_context(token))
        except Exception as e:
            raise _call_error(e) from None
        return _status(task)

    async def follow(self, task_id: str, token: str, *, poll_every: float = 10.0, give_up_after: float = 120.0,
                     on_drop=lambda reason: None) -> AsyncIterator[Status]:
        """Every new status of the seat's task, until it ends. Streams, and polls while the stream is down."""
        last, failing_since = None, None
        loop = asyncio.get_running_loop()
        while True:
            try:
                async for response in self._stream.subscribe(SubscribeToTaskRequest(id=task_id),
                                                             context=_context(token)):
                    failing_since = None
                    payload = getattr(response, response.WhichOneof("payload"))
                    if not hasattr(payload, "status"):
                        continue
                    status = _status(payload)
                    if status != last:
                        last = status
                        yield status
                    if status.state in TERMINAL:
                        return
            except NotAuthorised:
                raise
            except Exception as e:  # the stream dropped, or couldn't open: poll, then try again
                if isinstance(_call_error(e), NotAuthorised):
                    raise _call_error(e) from None
                on_drop(f"{type(e).__name__}: {e}"[:200])
            else:
                on_drop("the stream ended before the task did")
            try:
                status = await self.poll(task_id, token)
                failing_since = None
            except NotAuthorised:
                raise
            except DirectorError:
                failing_since = failing_since or loop.time()
                if loop.time() - failing_since > give_up_after:
                    raise DirectorError(f"lost contact with the director at {self.url} for {give_up_after:.0f} s")
                status = None
            if status is not None:
                if status != last:
                    last = status
                    yield status
                if status.state in TERMINAL:
                    return
            await asyncio.sleep(poll_every)


@contextlib.asynccontextmanager
async def director_client(url: str) -> AsyncIterator[DirectorClient]:
    client = DirectorClient(url)
    try:
        yield client
    finally:
        await client.close()

