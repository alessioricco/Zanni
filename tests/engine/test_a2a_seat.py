"""A seat's whole life over A2A, on loopback, against a fake director: every message checked against the schemas."""

import asyncio
import json
from pathlib import Path

import httpx
import jsonschema
import pytest

from zanni.director.contract import DirectorInfo, Outgoing
from zanni.engine.a2a_client import DirectorClient, NotAuthorised
from zanni.engine.a2a_server import director_app, listening
from zanni.engine.a2a_wire import as_json
from zanni.protocol.card import EXTENSION_URI
from zanni.engine.a2a_client import _status
from zanni.protocol.messages import Cast, Cue, Join, Refused, Release, Released, Report

SCHEMAS = Path(__file__).parents[2] / "docs" / "spec" / "schemas"
VALID = Path(__file__).parents[1] / "conformance" / "protocol" / "valid"
INFO = DirectorInfo(name="test director", description="A fake director", version="0.0.1", play="p", script="s")
JOIN_TOKEN, SEAT_TOKEN = "join-token-fake", "seat-token-fake"


def check_schema(message: dict) -> None:
    schema = json.loads((SCHEMAS / f"{message['kind']}.schema.json").read_text())
    jsonschema.validate(message, schema)


class FakeCasting:
    """Accepts one actor; its cues come from a queue the test fills. Records every message, as sent."""

    def __init__(self):
        self.outbox: asyncio.Queue[Outgoing] = asyncio.Queue()
        self.seen: list[dict] = []
        self.task_id = None
        self.contacts = 0
        self.streams = 0
        self.ending_with = Outgoing("canceled", Release(kind="zanni.release", reason="no-heartbeat"))
        self.revoked = False
        self.reached_at = None

    async def join(self, token, task_id, join, problem, reached_at):
        self.reached_at = reached_at
        if problem:
            reason, _, message = problem.partition(": ")
            return Refused(kind="zanni.refused", reason=reason, message=message)
        self.seen.append(as_json(join))
        if token != JOIN_TOKEN:
            return Refused(kind="zanni.refused", reason="not-authorised", message="the join token isn't this play's")
        self.task_id = task_id
        cast = Cast(kind="zanni.cast", seat="tester-1", part="tester", permissions={"read": ["/"], "write": ["tests/"]},
                    stage={"mcp_url": f"{reached_at}/stage/mcp", "token": "stage-token-fake"},
                    seat_token=SEAT_TOKEN, expires_at="2026-10-25T00:00:00Z")
        self.seen.append(as_json(cast))
        return cast

    async def next_for(self, task_id):
        out = await self.outbox.get()
        if out.message:
            self.seen.append(as_json(out.message))
        return out

    async def report(self, task_id, report):
        self.seen.append(as_json(report))

    async def released(self, task_id, released):
        self.seen.append(as_json(released))

    def ending(self, task_id):
        return self.ending_with

    def authorise(self, token, task_id):
        if self.revoked:
            return "the seat was released, and its token revoked"
        return None if token == SEAT_TOKEN and task_id == self.task_id else "this isn't the seat's token"

    def contact(self, task_id, streaming=None):
        self.contacts += 1
        self.streams += streaming is True

    def stage_for(self, token):
        return None


def actor_card() -> dict:
    params = json.loads((VALID / "actor-card.json").read_text())
    return {"name": "tester-1", "description": "Writes tests", "version": "1.4.0",
            "capabilities": {"extensions": [{"uri": EXTENSION_URI, "params": params}]},
            "defaultInputModes": ["application/json"], "defaultOutputModes": ["application/json"],
            "skills": [{"id": "write-test", "name": "write-test", "description": "Write a test", "tags": []}]}


async def raw_join(client, card) -> Refused:
    """Send a join our own actor would never send: Join's validator would stop it first."""
    task = await client._send_message(Join.model_construct(kind="zanni.join", card=card, part=None), JOIN_TOKEN)
    return _status(task).message


CUE = Cue(kind="zanni.cue", cue="c-1", scene="Specify", instructions="Write one test.")
REPORT = Report(kind="zanni.report", cue="c-1", outcome="done", summary="Wrote it.", changes=["1"], cost=None)


async def run_director(casting, body):
    handlers = []

    def app_for(url):
        app, handler = director_app(casting, INFO, url)
        handlers.append(handler)
        return app

    async with listening(app_for) as server:
        client = DirectorClient(server.url)
        try:
            await body(server, client, handlers[0])
        finally:
            await client.close()


def run(casting, body):
    asyncio.run(asyncio.wait_for(run_director(casting, body), 30))


def test_the_card_carries_the_extension_join_skill_and_bearer_scheme():
    async def body(server, client, handler):
        card = await client.fetch_card()
        ext = card["capabilities"]["extensions"][0]
        assert ext["uri"] == EXTENSION_URI and ext["required"] is True
        check_schema(ext["params"] | {"kind": "zanni.director-card"})
        assert [s["id"] for s in card["skills"]] == ["join"]
        assert card["securitySchemes"]["bearer"]["httpAuthSecurityScheme"]["scheme"] == "bearer"

    run(FakeCasting(), body)


def test_a_seat_from_join_to_release_matches_the_schemas():
    casting = FakeCasting()

    async def body(server, client, handler):
        await client.fetch_card()
        await casting.outbox.put(Outgoing("input-required", CUE))
        task_id, cast = await client.join(actor_card(), JOIN_TOKEN)
        assert isinstance(cast, Cast) and cast.seat == "tester-1"
        assert casting.reached_at == server.url  # the stage address is built from what the actor reached
        states = []
        async for status in client.follow(task_id, cast.seat_token, poll_every=0.1):
            states.append(status.state)
            if isinstance(status.message, Cue) and status.state == "input-required":
                await casting.outbox.put(Outgoing("input-required", Release(kind="zanni.release", reason="done")))
                await client.send(task_id, cast.seat_token, REPORT)
            elif isinstance(status.message, Release):
                await client.send(task_id, cast.seat_token, Released(kind="zanni.released", discarded=True))
        assert states[0] == "input-required" and states[-1] == "completed"
        assert casting.streams >= 1 and casting.contacts >= 3

    run(casting, body)
    kinds = [m["kind"] for m in casting.seen]
    assert kinds == ["zanni.join", "zanni.cast", "zanni.cue", "zanni.report", "zanni.release", "zanni.released"]
    for message in casting.seen:
        check_schema(message)


def test_a_wrong_join_token_is_refused_with_not_authorised():
    async def body(server, client, handler):
        await client.fetch_card()
        _, answer = await client.join(actor_card(), "not-the-token")
        assert isinstance(answer, Refused) and answer.reason == "not-authorised"

    run(FakeCasting(), body)


def test_a_card_without_the_extension_is_a_bad_card():
    async def body(server, client, handler):
        await client.fetch_card()
        answer = await raw_join(client, actor_card() | {"capabilities": {"extensions": []}})
        assert isinstance(answer, Refused) and answer.reason == "bad-card"

    run(FakeCasting(), body)


def test_a_card_on_another_version_is_unsupported():
    async def body(server, client, handler):
        await client.fetch_card()
        card = actor_card()
        card["capabilities"]["extensions"][0]["uri"] = EXTENSION_URI.replace("#v2", "#v3")
        answer = await raw_join(client, card)
        assert isinstance(answer, Refused) and answer.reason == "unsupported-version"

    run(FakeCasting(), body)


def test_a_seat_call_with_a_wrong_or_revoked_token_is_not_authorised():
    casting = FakeCasting()

    async def body(server, client, handler):
        await client.fetch_card()
        await casting.outbox.put(Outgoing("input-required", CUE))
        task_id, cast = await client.join(actor_card(), JOIN_TOKEN)
        with pytest.raises(NotAuthorised):
            await client.poll(task_id, "someone-elses-token")
        with pytest.raises(NotAuthorised):
            await client.send(task_id, JOIN_TOKEN, REPORT)
        casting.revoked = True
        with pytest.raises(NotAuthorised, match="revoked"):
            await client.poll(task_id, cast.seat_token)

    run(casting, body)


def test_calls_without_the_extension_header_and_listing_or_cancelling_tasks_are_refused():
    async def body(server, client, handler):
        async with httpx.AsyncClient() as http:
            rpc = {"jsonrpc": "2.0", "id": 1, "method": "ListTasks", "params": {}}
            listed = (await http.post(server.url + "/", json=rpc, headers={
                "A2A-Extensions": EXTENSION_URI, "A2A-Version": "1.0"})).json()
            assert "error" in listed
            rpc = {"jsonrpc": "2.0", "id": 2, "method": "GetTask", "params": {"id": "x"}}
            bare = (await http.post(server.url + "/", json=rpc, headers={"A2A-Version": "1.0"})).json()
            assert "error" in bare and EXTENSION_URI in bare["error"]["message"]

    run(FakeCasting(), body)


def test_the_director_ending_a_seat_reaches_the_actor():
    casting = FakeCasting()

    async def body(server, client, handler):
        await client.fetch_card()
        await casting.outbox.put(Outgoing("input-required", CUE))
        task_id, cast = await client.join(actor_card(), JOIN_TOKEN)
        statuses = []
        async for status in client.follow(task_id, cast.seat_token, poll_every=0.1):
            statuses.append(status)
            if status.state == "input-required":
                await handler.end(task_id)
        assert statuses[-1].state == "canceled"
        assert statuses[-1].message == Release(kind="zanni.release", reason="no-heartbeat")

    run(casting, body)


def test_a_dropped_stream_is_recovered_by_polling():
    casting = FakeCasting()

    async def body(server, client, handler):
        await client.fetch_card()
        await casting.outbox.put(Outgoing("input-required", CUE))
        task_id, cast = await client.join(actor_card(), JOIN_TOKEN)

        async def broken(*args, **kwargs):
            raise httpx.RemoteProtocolError("the stream dropped")
            yield  # pragma: no cover

        client._stream.subscribe = broken
        async for status in client.follow(task_id, cast.seat_token, poll_every=0.05):
            if isinstance(status.message, Cue):
                await casting.outbox.put(Outgoing("input-required", Release(kind="zanni.release", reason="done")))
                await client.send(task_id, cast.seat_token, REPORT)
            elif isinstance(status.message, Release):
                await client.send(task_id, cast.seat_token, Released(kind="zanni.released", discarded=True))
        assert casting.streams == 0 and casting.contacts >= 3  # every poll was contact

    run(casting, body)
