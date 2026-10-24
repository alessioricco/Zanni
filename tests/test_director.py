"""The director's casting side on its own: joins, refusals, tokens, cues, heartbeats and release (D29, D31)."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from zanni.actor.stage import FolderStage
from zanni.director.casting import Director, PartSlot, SeatLost
from zanni.director.contract import Outgoing
from zanni.files.hashing import package_hash
from zanni.log import Log
from zanni.protocol.card import EXTENSION_URI
from zanni.protocol.messages import Cast, Cue, Join, Refused, Released, Report

PARAMS = json.loads((Path(__file__).parent / "conformance/protocol/valid/actor-card.json").read_text())
JOIN_TOKEN = "join-token-fake"
URL = "http://director.example:8765"


def join_message(params=PARAMS, part=None) -> Join:
    card = {"name": "tester-1", "capabilities": {"extensions": [{"uri": EXTENSION_URI, "params": params}]}}
    return Join(kind="zanni.join", card=card, part=part)


def fits_tester(params):
    return None if params.role.name == "tester" else ("role-mismatch", f"this part is for tester, not {params.role.name}")


class Clock:
    def __init__(self):
        self.t, self.utc = 1000.0, datetime(2026, 10, 24, 12, 0, tzinfo=UTC)

    def advance(self, seconds):
        self.t += seconds
        self.utc += timedelta(seconds=seconds)


def director(tmp_path, *, seats=1, interval=1, clock=None):
    clock = clock or Clock()
    (tmp_path / "stage").mkdir(exist_ok=True)
    d = Director(join_token=JOIN_TOKEN, parts=[PartSlot("tester", fits_tester, seats)],
                 stage=FolderStage(tmp_path / "stage", [], []), log=Log(tmp_path / "log.jsonl", "r1"),
                 heartbeat_interval=interval, heartbeat_misses=3, clock=lambda: clock.t, utcnow=lambda: clock.utc)
    return d, clock


def events(tmp_path) -> list[dict]:
    return [json.loads(line) for line in (tmp_path / "log.jsonl").read_text().splitlines()]


def test_a_join_is_cast_with_fresh_tokens_and_the_roles_needs_as_permissions(tmp_path):
    async def go():
        d, _ = director(tmp_path)
        cast = await d.join(JOIN_TOKEN, "task-1", join_message(), None, URL)
        assert isinstance(cast, Cast) and cast.seat == "tester-1" and cast.part == "tester"
        assert cast.stage.mcp_url == f"{URL}/stage/mcp"
        assert cast.seat_token != cast.stage.token and JOIN_TOKEN not in (cast.seat_token, cast.stage.token)
        assert cast.permissions.write == PARAMS["role"]["needs"]["stage_write"]
        assert cast.expires_at == "2026-10-25T12:00:00Z" and cast.heartbeat.interval == "1"
        return cast

    cast = asyncio.run(go())
    log = (tmp_path / "log.jsonl").read_text()
    assert '"event": "actor-joined"' in log and cast.seat_token not in log and cast.stage.token not in log


@pytest.mark.parametrize("token,join,problem,reason", [
    (None, join_message(), None, "not-authorised"),
    ("wrong", join_message(), None, "not-authorised"),
    (JOIN_TOKEN, None, "bad-card: the card isn't an A2A Agent Card", "bad-card"),
    (JOIN_TOKEN, None, "unsupported-version: v2 only", "unsupported-version"),
    (JOIN_TOKEN, join_message(PARAMS | {"role": PARAMS["role"] | {"name": "coder"}}), None, "role-mismatch"),
    (JOIN_TOKEN, join_message(part="editor"), None, "no-such-part"),
])
def test_joins_are_refused_with_the_specified_reasons(tmp_path, token, join, problem, reason):
    d, _ = director(tmp_path)
    answer = asyncio.run(d.join(token, "task-1", join, problem, URL))
    assert isinstance(answer, Refused) and answer.reason == reason
    assert events(tmp_path)[-1]["event"] == "join-refused" and events(tmp_path)[-1]["reason"] == reason


def test_a_full_part_refuses_the_next_actor(tmp_path):
    async def go():
        d, _ = director(tmp_path, seats=1)
        await d.join(JOIN_TOKEN, "task-1", join_message(), None, URL)
        return await d.join(JOIN_TOKEN, "task-2", join_message(), None, URL)

    assert asyncio.run(go()).reason == "part-full"


def test_a_cue_waits_for_its_report_and_a_report_for_another_cue_is_ignored(tmp_path):
    async def go():
        d, _ = director(tmp_path)
        await d.join(JOIN_TOKEN, "task-1", join_message(), None, URL)
        seat = await d.wait_for_seat("tester")
        cue = Cue(kind="zanni.cue", cue="c-1", scene="Specify", instructions="Write a test.")
        waiting = asyncio.create_task(d.cue(seat, cue))
        assert (await d.next_for("task-1")) == Outgoing("input-required", cue)
        await d.report("task-1", Report(kind="zanni.report", cue="c-9", outcome="done", summary="?", cost=None))
        assert not waiting.done()
        report = Report(kind="zanni.report", cue="c-1", outcome="done", summary="Wrote it.", changes=["1"],
                        cost={"amount": "0.0007", "currency": "USD"})
        await d.report("task-1", report)
        return await waiting

    assert asyncio.run(go()).summary == "Wrote it."
    kinds = [e["event"] for e in events(tmp_path)]
    assert kinds == ["actor-joined", "cue", "report-ignored", "report", "cost"]
    assert events(tmp_path)[-1]["amount"] == "0.0007"


def test_the_seat_token_is_checked_for_its_task_its_expiry_and_its_release(tmp_path):
    async def go():
        d, clock = director(tmp_path)
        cast = await d.join(JOIN_TOKEN, "task-1", join_message(), None, URL)
        assert d.authorise(cast.seat_token, "task-1") is None
        assert d.authorise(cast.stage.token, "task-1") and d.authorise(cast.seat_token, "task-2")
        assert d.stage_for(cast.stage.token) is not None and d.stage_for(cast.seat_token) is None
        clock.advance(24 * 3600)
        assert "expired" in d.authorise(cast.seat_token, "task-1") and d.stage_for(cast.stage.token) is None
        return d, cast

    d, cast = asyncio.run(go())
    d2, _ = director(tmp_path)

    async def released():
        cast = await d2.join(JOIN_TOKEN, "task-1", join_message(), None, URL)
        seat = await d2.wait_for_seat("tester")
        releasing = asyncio.create_task(d2.release(seat))
        out = await d2.next_for("task-1")
        assert out.message.reason == "done"
        await d2.released("task-1", Released(kind="zanni.released", discarded=True))
        assert await releasing is True
        return cast

    cast = asyncio.run(released())
    assert "revoked" in d2.authorise(cast.seat_token, "task-1")
    assert d2.stage_for(cast.stage.token) is None


def test_a_release_with_no_answer_completes_the_task_and_revokes_anyway(tmp_path):
    ended = []

    async def go():
        d, _ = director(tmp_path, interval=1)

        async def end(task_id):
            ended.append((task_id, d.ending(task_id)))
        d.end_task = end
        cast = await d.join(JOIN_TOKEN, "task-1", join_message(), None, URL)
        seat = await d.wait_for_seat("tester")
        assert await d.release(seat) is False
        return d, cast

    d, cast = asyncio.run(go())
    assert ended == [("task-1", Outgoing("completed"))]
    assert d.authorise(cast.seat_token, "task-1") is not None


def test_a_seat_with_no_heartbeat_is_ended_and_its_cue_fails(tmp_path):
    ended = []

    async def go():
        d, clock = director(tmp_path, interval=1)

        async def end(task_id):
            ended.append(d.ending(task_id))
        d.end_task = end
        cast = await d.join(JOIN_TOKEN, "task-1", join_message(), None, URL)
        seat = await d.wait_for_seat("tester")
        d.contact("task-1", streaming=True)
        clock.advance(10)
        assert d.overdue() == []  # an open stream is contact (D31)
        d.contact("task-1", streaming=False)
        clock.advance(4)
        assert d.overdue() == [seat]
        cue = asyncio.create_task(d.cue(seat, Cue(kind="zanni.cue", cue="c-1", scene="S", instructions="x")))
        watcher = asyncio.create_task(d.watch(every=0.01))
        with pytest.raises(SeatLost, match="no-heartbeat"):
            await cue
        watcher.cancel()
        return d, cast

    d, cast = asyncio.run(go())
    assert ended[0].state == "canceled" and ended[0].message.reason == "no-heartbeat"
    assert "revoked" in d.authorise(cast.seat_token, "task-1")
    assert events(tmp_path)[-1] | {"ts": None} == {"ts": None, "run": "r1", "event": "seat-released",
                                                   "seat": "tester-1", "reason": "no-heartbeat"}


def test_a_missed_deadline_counts_as_a_missed_heartbeat(tmp_path):
    async def go():
        d, clock = director(tmp_path)
        await d.join(JOIN_TOKEN, "task-1", join_message(), None, URL)
        seat = await d.wait_for_seat("tester")
        d.contact("task-1", streaming=True)
        asyncio.create_task(d.cue(seat, Cue(kind="zanni.cue", cue="c-1", scene="S", instructions="x",
                                            deadline="2026-10-24T12:00:05Z")))
        await asyncio.sleep(0)
        clock.advance(6)
        return d.overdue() == [seat]

    assert asyncio.run(go())


def test_the_package_hash_is_the_sha256sum_listing(tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "a.txt").write_text("one\n")
    (tmp_path / "b" / "c.md").write_text("two\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ignored")
    listing = "".join(f"{hashlib.sha256(t.encode()).hexdigest()}  {p}\n" for p, t in [("a.txt", "one\n"), ("b/c.md", "two\n")])
    assert package_hash(tmp_path) == "sha256:" + hashlib.sha256(listing.encode()).hexdigest()
