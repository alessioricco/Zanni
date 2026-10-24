"""What a stage backend is (D43): storage only. It never sees a seat's token, and never decides who may do what.

The director puts one layer above every backend (src/zanni/stage/layer.py), which checks paths and permissions,
and keeps the record of who changed what. `author` and `note` are labels, so a backend such as git can write them
into its history. A backend raises StageError with `not-found`, `unavailable`, `not-text`, or `invalid-path` for a
path it can't store (such as `.git/`).
"""

from __future__ import annotations  # `list` is a method name below; Python < 3.14 evaluates annotations eagerly

from pathlib import Path
from typing import Protocol


class StageBackend(Protocol):
    kind: str  # "folder", "git" or "mcp", as in the play file

    async def read(self, path: str) -> str: ...

    async def write(self, path: str, content: str, *, author: str | None, note: str | None) -> str:
        """Store a file; returns the backend's own marker for this change."""

    async def delete(self, path: str, *, author: str | None, note: str | None) -> str: ...

    async def list(self, folder: str = "") -> list[str]:
        """Every file under a folder ("" for the root), as stage paths; not-found if it isn't a folder."""

    async def changes(self, since: str | None = None) -> tuple[list[tuple[str, str]], str]:
        """The backend's own view of what changed since one of its markers, and its current marker."""

    async def snapshot(self, into: Path) -> str:
        """Write every file of the stage into the empty folder `into`; returns the backend's current marker."""

    async def close(self) -> None: ...
