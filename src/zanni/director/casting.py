"""The director's casting side (D29): joins, seats and their tokens, cues and reports, heartbeats and release.

Plain Zanni code, no engine imports: the engine's A2A server calls the `Casting` methods below, and whatever
drives the play (a rehearsal, or a play's production in play.py) calls `wait_for_seat`, `cue` and `release`.
Every limit here is enforced by the director (golden rule 5): a seat whose token is revoked can do nothing.
"""

import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from zanni.actor.stage import FolderStage
from zanni.director.contract import Outgoing
from zanni.log import Log
from zanni.protocol.card import EXTENSION_URI, ActorCardParams
from zanni.protocol.encoding import Timestamp
from zanni.protocol.messages import Cast, Cue, Join, Refused, Release, Released, Report

# What decides whether an actor's card fits a part: None, or a (reason, message) refusal (protocol/fit.py).
Fit = Callable[[ActorCardParams], tuple[str, str] | None]


@dataclass
class PartSlot:
    name: str
    fit: Fit
    seats: int = 1


class SeatLost(Exception):
    """The seat ended before it answered: no heartbeat, a missed deadline, or the director stopped it."""

    def __init__(self, seat: str, reason: str):
        super().__init__(f"seat {seat} ended: {reason}")
        self.seat, self.reason = seat, reason


@dataclass
class Seat:
    id: str
    part: str
    task_id: str
    actor: str | None
    role: str
    seat_token: str
    stage_token: str
    expires_at: datetime
    stage: FolderStage
    last_contact: float
    host: str | None = None  # the address it joined from (max_seats_per_host)
    cue_marker: int = 0  # the stage's record length when the pending cue was sent (D41)
    streams: int = 0
    outbox: asyncio.Queue = field(default_factory=asyncio.Queue)
    pending: tuple[Cue, asyncio.Future] | None = None
    deadline: datetime | None = None
    released: asyncio.Event = field(default_factory=asyncio.Event)
    ended: Outgoing | None = None  # set once the director ends the task itself
    revoked: bool = False
    reason: str | None = None  # why the seat ended

    @property
    def active(self) -> bool:
        return not self.revoked


def stamp(when: datetime) -> Timestamp:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def card_params(join: Join) -> ActorCardParams:
    ours = [e for e in join.card["capabilities"]["extensions"] if e.get("uri") == EXTENSION_URI]
    return ActorCardParams.model_validate(ours[0]["params"])


class Director:
    """One play's casting: its parts, its seats, and the play's log."""

    def __init__(self, *, join_token: str, parts: list[PartSlot], stage: FolderStage, log: Log,
                 heartbeat_interval: int = 30, heartbeat_misses: int = 3, token_ttl: timedelta = timedelta(hours=24),
                 clock: Callable[[], float] = time.monotonic, utcnow: Callable[[], datetime] = lambda: datetime.now(UTC),
                 say: Callable[[str], None] = lambda _: None, max_per_host: int | None = None,
                 require_pricing: bool = False):
        self.join_token = join_token
        self.parts = {p.name: p for p in parts}
        self.stage, self.log = stage, log
        self.interval, self.misses = heartbeat_interval, heartbeat_misses
        self.token_ttl, self.clock, self.utcnow, self.say = token_ttl, clock, utcnow, say
        self.max_per_host = max_per_host
        self.require_pricing = require_pricing  # the play has a budget: unpriced actors are refused (D39)
        self.seats: dict[str, Seat] = {}  # by task id
        self.cast_event = asyncio.Event()
        self.end_task: Callable[[str], Awaitable[None]] | None = None  # set by the server: ends an A2A task

    # --- The Casting interface (src/zanni/director/contract.py), called by the engine's A2A server

    def _refuse(self, reason: str, message: str, actor: str | None = None, role: str | None = None) -> Refused:
        self.log.event("join-refused", reason=reason, actor=actor, role=role)
        self.say(f"Refused a join: {reason} ({message})")
        return Refused(kind="zanni.refused", reason=reason, message=message)

    async def join(self, token, task_id, join, problem, reached_at, peer=None):
        if not token or not secrets.compare_digest(token, self.join_token):
            return self._refuse("not-authorised", "the join token is missing, or isn't this play's")
        if problem:
            reason, _, message = problem.partition(": ")
            return self._refuse(reason, message)
        params = card_params(join)
        who = dict(actor=params.actor or join.card.get("name"), role=params.role.ref)
        if self.require_pricing and join.pricing != "known":
            return self._refuse("unpriced", "this play has a budget, and the actor's models aren't all priced, so "
                                            "its cost would be unknown; add `price:` to each model entry in its "
                                            "configuration (D7)", **who)
        if join.part is not None and join.part not in self.parts:
            return self._refuse("no-such-part", f"this play has no part {join.part!r}; its parts are: "
                                                f"{', '.join(self.parts)}", **who)
        if self.max_per_host is not None and peer is not None:
            on_host = sum(1 for s in self.seats.values() if s.active and s.host == peer)
            if on_host >= self.max_per_host:
                return self._refuse("host-cap", f"{on_host} seat(s) are already cast on {peer}, and the play allows "
                                                f"{self.max_per_host} per host (max_seats_per_host)", **who)
        candidates = [self.parts[join.part]] if join.part else list(self.parts.values())
        refusal = None
        for slot in candidates:
            refusal = slot.fit(params)
            if refusal is None:
                taken = sum(1 for s in self.seats.values() if s.part == slot.name and s.active)
                if taken >= slot.seats:
                    refusal = ("part-full", f"the part {slot.name} has all its {slot.seats} seat(s) taken")
                    continue
                return self._cast(slot, task_id, params, join, reached_at, peer)
        return self._refuse(*refusal, **who)

    def _cast(self, slot: PartSlot, task_id: str, params: ActorCardParams, join: Join, reached_at: str,
              peer: str | None = None) -> Cast:
        number = sum(1 for s in self.seats.values() if s.part == slot.name) + 1
        seat_id = f"{slot.name}-{number}"
        needs = params.role.needs
        seat = Seat(id=seat_id, part=slot.name, task_id=task_id, actor=params.actor or join.card.get("name"),
                    role=params.role.ref, seat_token=secrets.token_urlsafe(32), stage_token=secrets.token_urlsafe(32),
                    expires_at=self.utcnow() + self.token_ttl, last_contact=self.clock(), host=peer,
                    stage=self.stage.seat(needs.stage_read, needs.stage_write, seat_id))
        self.seats[task_id] = seat
        self.log.event("actor-joined", seat=seat_id, part=slot.name, role=seat.role, actor=seat.actor,
                       models=[m.model_dump() for m in params.models])  # self-reported (D11)
        self.say(f"Cast {seat.actor or 'an actor'} ({params.role.name} {params.role.version}) as {seat_id}")
        self.cast_event.set()
        return Cast(kind="zanni.cast", seat=seat_id, part=slot.name,
                    permissions={"read": needs.stage_read, "write": needs.stage_write},
                    stage={"mcp_url": f"{reached_at}/stage/mcp", "token": seat.stage_token},
                    seat_token=seat.seat_token, expires_at=stamp(seat.expires_at),
                    heartbeat={"interval": str(self.interval), "misses": str(self.misses)})

    async def next_for(self, task_id: str) -> Outgoing:
        return await self.seats[task_id].outbox.get()

    async def report(self, task_id: str, report: Report) -> None:
        seat = self.seats[task_id]
        if seat.pending is None or seat.pending[0].cue != report.cue:
            self.log.event("report-ignored", seat=seat.id, cue=report.cue, detail="no such cue is waiting")
            return
        cue, answer = seat.pending
        seat.pending, seat.deadline = None, None
        # The seat's own changes, from the stage's record, not the actor's list (D41)
        report = report.model_copy(update={"changes": self.stage.made_by(seat.id, seat.cue_marker)})
        self.log.event("report", seat=seat.id, scene=cue.scene, cue=report.cue, outcome=report.outcome,
                       summary=report.summary, changes=report.changes)
        self.log.event("cost", seat=seat.id, model=report.models[0].model if report.models else None,
                       amount=report.cost.amount if report.cost else None)  # self-reported (D7)
        if not answer.done():
            answer.set_result(report)

    async def released(self, task_id: str, released: Released) -> None:
        self.seats[task_id].released.set()

    def ending(self, task_id: str) -> Outgoing:
        seat = self.seats.get(task_id)
        return seat.ended if seat and seat.ended else Outgoing("canceled")

    def _seat_by(self, token: str | None, attr: str) -> Seat | None:
        for seat in self.seats.values():
            if token and secrets.compare_digest(getattr(seat, attr), token):
                return seat
        return None

    def authorise(self, token: str | None, task_id: str) -> str | None:
        seat = self.seats.get(task_id)
        if seat is None or not token or not secrets.compare_digest(seat.seat_token, token):
            return "this call needs the seat token this task's cast gave"
        if seat.revoked:
            return f"the seat {seat.id} was released ({seat.reason}), and its tokens revoked"
        if self.utcnow() >= seat.expires_at:
            return f"the seat {seat.id}'s token expired at {stamp(seat.expires_at)}"
        return None

    def contact(self, task_id: str, streaming: bool | None = None) -> None:
        seat = self.seats.get(task_id)
        if seat is None:
            return
        seat.last_contact = self.clock()
        if streaming is not None:
            seat.streams = max(0, seat.streams + (1 if streaming else -1))

    def stage_for(self, stage_token: str):
        seat = self._seat_by(stage_token, "stage_token")
        if seat is None or seat.revoked or self.utcnow() >= seat.expires_at:
            return None
        return seat.stage

    # --- Driving the play: called by a rehearsal, or by a play's production (play.py)

    async def wait_for_seat(self, part: str) -> Seat:
        while True:
            for seat in self.seats.values():
                if seat.part == part and seat.active:
                    return seat
            self.cast_event.clear()
            await self.cast_event.wait()

    async def cue(self, seat: Seat, cue: Cue) -> Report:
        """Send one cue and wait for its report; raises SeatLost if the seat ends first."""
        if seat.revoked:
            raise SeatLost(seat.id, seat.reason or "released")
        answer = asyncio.get_running_loop().create_future()
        seat.pending = (cue, answer)
        seat.cue_marker = len(self.stage.record)
        seat.deadline = datetime.fromisoformat(cue.deadline.replace("Z", "+00:00")) if cue.deadline else None
        self.log.event("cue", seat=seat.id, scene=cue.scene, cue=cue.cue,
                       budget=cue.limits.budget.amount if cue.limits.budget else None)
        await seat.outbox.put(Outgoing("input-required", cue))
        return await answer

    async def release(self, seat: Seat, reason: str = "done", message: str = "") -> bool:
        """End a seat: send zanni.release, wait one heartbeat interval for zanni.released, then revoke anyway.

        True if the actor confirmed. Revoking the tokens is what enforces the release, not the answer.
        """
        if seat.revoked:
            return False
        await seat.outbox.put(Outgoing("input-required", Release(kind="zanni.release", reason=reason, message=message)))
        try:
            await asyncio.wait_for(seat.released.wait(), self.interval)
            confirmed = True
        except TimeoutError:
            confirmed = False
            await self._end(seat, Outgoing("completed"), reason)
        self._revoke(seat, reason)
        return confirmed

    def _revoke(self, seat: Seat, reason: str) -> None:
        if seat.revoked:
            return
        seat.revoked, seat.reason = True, reason
        self.log.event("seat-released", seat=seat.id, reason=reason)
        self.say(f"Released {seat.id} ({reason})")

    async def _end(self, seat: Seat, status: Outgoing, reason: str) -> None:
        seat.ended = status
        if seat.pending and not seat.pending[1].done():
            seat.pending[1].set_exception(SeatLost(seat.id, reason))
        if self.end_task is not None:
            await self.end_task(seat.task_id)

    async def lose(self, seat: Seat, why: str) -> None:
        """End a seat the director knows is gone, such as a local seat whose process exited: as a missed heartbeat."""
        if seat.revoked:
            return
        release = Release(kind="zanni.release", reason="no-heartbeat", message=why)
        self._revoke(seat, "no-heartbeat")
        await self._end(seat, Outgoing("canceled", release), "no-heartbeat")

    def overdue(self) -> list[Seat]:
        """Active seats past their heartbeat, or past a cue's deadline (casting-extension.md, "Heartbeats")."""
        limit = self.interval * self.misses
        now, utc = self.clock(), self.utcnow()
        return [s for s in self.seats.values() if s.active and (
            (s.streams == 0 and now - s.last_contact > limit) or (s.deadline is not None and utc > s.deadline))]

    async def watch(self, every: float | None = None) -> None:
        """Run until cancelled: end every overdue seat as `canceled`, with a `no-heartbeat` release, and revoke it."""
        while True:
            await asyncio.sleep(every if every is not None else max(1.0, self.interval / 3))
            for seat in self.overdue():
                release = Release(kind="zanni.release", reason="no-heartbeat",
                                  message=f"no contact for {self.interval * self.misses} s, or a missed deadline")
                self._revoke(seat, "no-heartbeat")
                await self._end(seat, Outgoing("canceled", release), "no-heartbeat")
