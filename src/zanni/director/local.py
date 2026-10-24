"""Local seats (D36): actor configurations the director starts as subprocesses, `zanni <config> --play <url>`.

Each actor keeps its own models, credentials and log; the director reads only each file's `name` and `role`, and
never its credentials. Each subprocess watches a pipe from the director (its stdin) and exits when it closes, so a
director that dies leaves nothing spending. A seat that dies is restarted at most twice per play.
"""

import asyncio
import contextlib
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from zanni.director.casting import VERIFIER_PART
from zanni.log import Log

RESTARTS = 2
RELEASED_GRACE = 5  # seconds a released seat has to exit on its own before its pipe is closed


@dataclass
class LocalSeat:
    part: str
    config: Path
    name: str  # the configuration's `name`: the actor's name on its card, so the director can tell its seat
    proc: asyncio.subprocess.Process | None = None
    restarts: int = 0
    expected_exit: bool = False  # released, or stopped by the director: its exit isn't a crash
    watcher: asyncio.Task | None = field(default=None, repr=False)


class LocalSeats:
    def __init__(self, seats: dict[str, list[tuple[Path, str]]], *, join_token: str, log: Log, out_dir: Path,
                 say: Callable[[str], None] = print, on_exit: Callable[[str], Awaitable[None]] | None = None,
                 verifier_token: str | None = None):
        self.seats = {part: [LocalSeat(part, path, name) for path, name in files] for part, files in seats.items()}
        self.join_token, self.log, self.out_dir, self.say = join_token, log, out_dir, say
        self.verifier_token = verifier_token  # for local verifier seats only, in place of the join token (D45)
        self.on_exit = on_exit
        self.url: str | None = None  # the director's own address, once it listens
        self.stopping = False

    def all(self) -> list[LocalSeat]:
        return [s for seats in self.seats.values() for s in seats]

    def listed(self, part: str) -> int:
        return len(self.seats.get(part, []))

    def started(self, part: str) -> int:
        return sum(1 for s in self.seats.get(part, []) if not self._free(s))

    @staticmethod
    def _free(seat: LocalSeat) -> bool:
        """Never started, or released: the director may start it again for a later scene."""
        return seat.proc is None or seat.expected_exit

    def by_name(self, name: str | None) -> LocalSeat | None:
        return next((s for s in self.all() if s.name == name), None)

    async def start(self, part: str, n: int) -> int:
        """Start up to `n` of the part's listed seats that aren't running (never started, or released); returns how
        many started. A released seat is waited for, or stopped, before it starts again."""
        new = [s for s in self.seats.get(part, []) if self._free(s)][:n]
        for seat in new:
            await self._end(seat)
            await self._spawn(seat)
        return len(new)

    async def _spawn(self, seat: LocalSeat) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        out = (self.out_dir / f"{seat.name}.out").open("a")
        # Unbuffered, so its output reaches the file as it happens, even if it is stopped through its pipe.
        token = (("ZANNI_VERIFIER_TOKEN", self.verifier_token) if seat.part == VERIFIER_PART
                 else ("ZANNI_JOIN_TOKEN", self.join_token))
        env = {**os.environ, token[0]: token[1] or "", "ZANNI_WATCH_STDIN": "1", "PYTHONUNBUFFERED": "1"}
        seat.expected_exit = False
        seat.proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "zanni", str(seat.config), "--play", self.url, stdin=asyncio.subprocess.PIPE,
            stdout=out, stderr=asyncio.subprocess.STDOUT, env=env, cwd=seat.config.parent)
        out.close()
        self.log.event("seat-started", seat=seat.name, part=seat.part, pid=seat.proc.pid)
        self.say(f"  started the local seat {seat.name} ({seat.part})")
        seat.watcher = asyncio.create_task(self._watch(seat, seat.proc))

    async def _watch(self, seat: LocalSeat, proc: asyncio.subprocess.Process) -> None:
        code = await proc.wait()
        self.log.event("seat-exited", seat=seat.name, part=seat.part, exit_code=code)
        if seat.expected_exit or self.stopping or seat.proc is not proc:
            return
        self.say(f"  the local seat {seat.name} exited (code {code})")
        if self.on_exit is not None:
            await self.on_exit(seat.name)

    async def restart(self, name: str | None, reason: str) -> bool:
        """Restart a local seat that was lost, at most RESTARTS times per play. False if it isn't local, or is spent."""
        seat = self.by_name(name)
        if seat is None or self.stopping:
            return False
        if seat.restarts >= RESTARTS:
            self.log.event("seat-not-restarted", seat=seat.name, reason=f"restarted {RESTARTS} times already")
            self.say(f"  {seat.name} was lost again ({reason}); it was restarted {RESTARTS} times, so its part waits "
                     "for an actor to join")
            return False
        await self._end(seat)
        seat.restarts += 1
        self.say(f"  restarting {seat.name} ({reason}); restart {seat.restarts} of {RESTARTS}")
        await self._spawn(seat)
        return True

    def released(self, name: str | None) -> None:
        if seat := self.by_name(name):
            seat.expected_exit = True

    async def _end(self, seat: LocalSeat, grace: float = 10) -> None:
        """Close its pipe (it exits at once), then kill it if it hasn't after `grace` seconds. A released seat is first
        given a few seconds to see its release and exit on its own, so its exit code says how it ended."""
        proc = seat.proc
        if proc is None or proc.returncode is not None:
            return
        if seat.expected_exit:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(proc.wait(), RELEASED_GRACE)
            if proc.returncode is not None:
                return
        seat.expected_exit = True
        with contextlib.suppress(Exception):
            proc.stdin.close()
        try:
            await asyncio.wait_for(proc.wait(), grace)
        except TimeoutError:
            proc.kill()
            await proc.wait()

    async def stop_all(self, grace: float = 10) -> None:
        self.stopping = True
        await asyncio.gather(*[self._end(s, grace) for s in self.all()])
        for seat in self.all():
            if seat.watcher:
                with contextlib.suppress(asyncio.CancelledError):
                    await seat.watcher
