"""The layer the director puts above every stage backend (D43): paths, each seat's permissions, and the record.

Enforcement lives here, once, for every backend, never in a prompt and never in the backend (golden rule 5). The
record is append-only and says which seat made each change, so a report holds only its own seat's changes (D41);
change markers are positions in it, the same on every backend. Writes are applied one at a time, in the order the
director receives them (D44).
"""

from __future__ import annotations  # `list` is a method name below; Python < 3.14 evaluates annotations eagerly

import asyncio
from dataclasses import dataclass
from pathlib import Path

from zanni.files.schemas import covers
from zanni.stage.backend import StageBackend
from zanni.stage.errors import StageError
from zanni.stage.paths import check_path


@dataclass(frozen=True)
class Change:
    path: str
    change: str  # "written" or "deleted"
    seat: str | None  # who made it; None for the director's own changes
    note: str | None  # the cue it was made for
    backend_marker: str  # the backend's own marker: a commit hash, a server's marker


class Stage:
    """A play's stage: one backend, one record, and a view per seat."""

    def __init__(self, backend: StageBackend):
        self.backend = backend
        self.record: list[Change] = []
        self._lock: tuple[asyncio.AbstractEventLoop, asyncio.Lock] | None = None

    def _writing(self) -> asyncio.Lock:
        """One lock per event loop: a stage may outlive the loop it was first used in (as in tests)."""
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock[0] is not loop:
            self._lock = (loop, asyncio.Lock())
        return self._lock[1]

    @property
    def kind(self) -> str:
        return self.backend.kind

    def marker(self) -> int:
        """The current change marker: how many changes the record holds."""
        return len(self.record)

    def seat(self, read: list[str], write: list[str], who: str | None = None) -> SeatStage:
        """One seat's view: the same stage and record, with that seat's permissions."""
        return SeatStage(self, read, write, who)

    def made_by(self, who: str, since: int) -> list[str]:
        """The change markers of the changes `who` made after the marker `since` (D41)."""
        return [str(i + 1) for i, c in enumerate(self.record) if i >= since and c.seat == who]

    def changed_since(self, since: int) -> list[str]:
        return sorted({c.path for c in self.record[since:]})

    async def missing(self, expects: list[str]) -> list[str]:
        """The script's `stage.expects` paths the stage doesn't hold: a file, or a folder holding a file."""
        files = await self.backend.list("")
        return [p for p in expects if not any(f == p.rstrip("/") or f.startswith(p.rstrip("/") + "/") for f in files)]

    async def snapshot(self, into: Path) -> int:
        """The stage as a real folder, for a verifier (D45); returns the marker it was taken at."""
        async with self._writing():  # no write lands half-way through
            await self.backend.snapshot(into)
            return self.marker()

    async def apply(self, path: str, content: str | None, who: str | None, note: str | None) -> str:
        """Write (content) or delete (None), and record it; one at a time, in the order received (D44)."""
        async with self._writing():
            if content is None:
                own = await self.backend.delete(path, author=who, note=note)
            else:
                own = await self.backend.write(path, content, author=who, note=note)
            self.record.append(Change(path, "deleted" if content is None else "written", who, note, own))
            return str(self.marker())

    async def close(self) -> None:
        await self.backend.close()


class SeatStage:
    """The five stage operations (docs/spec/stage.md) for one seat, checked against its permissions."""

    def __init__(self, stage: Stage, read: list[str], write: list[str], who: str | None):
        self.stage = stage
        self.read_rules = list(read) + list(write)  # writing implies reading
        self.write_rules = list(write)
        self.who = who
        self.note: str | None = None  # the cue this seat is working on, written into the backend's history
        self.cue_writes: list[str] | None = None  # the pending cue's `writes`, narrowing the seat's own (D54)
        self.refused: list[str] = []  # writes and deletes refused since the cue began, for its report (D52)

    def _may(self, rules: list[str], path: str) -> bool:
        return any(covers(rule, path) for rule in rules)

    def _allow(self, path: str, rules: list[str], verb: str) -> str:
        check_path(path)
        if not self._may(rules, path):
            raise StageError("not-permitted", f"this seat may not {verb} {path}; it may {verb}: "
                                              f"{', '.join(rules) or 'nothing'}")
        return path

    async def read(self, path: str) -> str:
        return await self.stage.backend.read(self._allow(path, self.read_rules, "read"))

    def _allow_change(self, path: str, verb: str) -> str:
        """A write or delete: within the seat's permissions and, while a cue names its `writes`, within those too.
        A refusal is recorded for the cue's report."""
        try:
            self._allow(path, self.write_rules, verb)
            if self.cue_writes is not None and not self._may(self.cue_writes, path):
                raise StageError("not-permitted", f"this cue may not {verb} {path}; it may {verb}: "
                                                  f"{', '.join(self.cue_writes) or 'nothing'}")
        except StageError as e:
            if e.code == "not-permitted":
                self.refused.append(f"{verb} {path}")
            raise
        return path

    def start_cue(self, note: str, writes: list[str]) -> None:
        """A cue begins: its note goes into the backend's history; its `writes`, if it names any, narrow the seat's."""
        self.note, self.cue_writes, self.refused = note, (list(writes) or None), []

    def end_cue(self) -> list[str]:
        """The cue is answered, or lost: the seat's own permissions apply again. Returns what was refused."""
        refused, self.cue_writes, self.refused = self.refused, None, []
        return refused

    async def write(self, path: str, content: str) -> str:
        return await self.stage.apply(self._allow_change(path, "write"), content, self.who, self.note)

    async def delete(self, path: str) -> str:
        return await self.stage.apply(self._allow_change(path, "delete"), None, self.who, self.note)

    async def list(self, path: str = "") -> list[str]:
        folder = path.rstrip("/")
        if folder:
            check_path(folder)
        return [f for f in await self.stage.backend.list(folder) if self._may(self.read_rules, f)]

    async def changes(self, since: str | None = None) -> tuple[list[tuple[str, str]], str]:
        record = self.stage.record
        start = 0
        if since is not None:
            if not since.isdigit() or int(since) > len(record):
                raise StageError("unknown-marker", f"{since!r} is not a change marker this stage gave")
            start = int(since)
        visible = [(c.path, c.change) for c in record[start:] if self._may(self.read_rules, c.path)]
        return visible, str(len(record))
