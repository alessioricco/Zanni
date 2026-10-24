"""The `folder` backend (docs/spec/stage.md): a folder on the director's machine. Storage only (D43)."""

from __future__ import annotations  # `list` is a method name below; Python < 3.14 evaluates annotations eagerly

import shutil
from pathlib import Path

from zanni.stage.errors import StageError


class FolderBackend:
    kind = "folder"

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.log: list[tuple[str, str]] = []  # (path, change): its own markers are positions in it

    def _file(self, path: str) -> Path:
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):  # a symlink pointing out of the stage
            raise StageError("invalid-path", f"{path} leads outside the stage")
        return target

    async def read(self, path: str) -> str:
        target = self._file(path)
        if not target.is_file():
            raise StageError("not-found", f"{path} doesn't exist on the stage")
        try:
            return target.read_text()
        except UnicodeDecodeError:
            raise StageError("not-text", f"{path} isn't a text file; the stage carries text only") from None

    async def write(self, path: str, content: str, *, author: str | None = None, note: str | None = None) -> str:
        target = self._file(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        self.log.append((path, "written"))
        return str(len(self.log))

    async def delete(self, path: str, *, author: str | None = None, note: str | None = None) -> str:
        target = self._file(path)
        if not target.is_file():
            raise StageError("not-found", f"{path} doesn't exist on the stage")
        target.unlink()
        self.log.append((path, "deleted"))
        return str(len(self.log))

    async def list(self, folder: str = "") -> list[str]:
        base = (self.root / folder).resolve()
        if not base.is_dir() or not base.is_relative_to(self.root):
            raise StageError("not-found", f"{folder or 'the stage root'} is not a folder on the stage")
        return [p.relative_to(self.root).as_posix() for p in sorted(base.rglob("*")) if p.is_file()]

    async def changes(self, since: str | None = None) -> tuple[list[tuple[str, str]], str]:
        start = int(since) if since and since.isdigit() else 0
        return self.log[start:], str(len(self.log))

    async def snapshot(self, into: Path) -> str:
        shutil.copytree(self.root, into, dirs_exist_ok=True, symlinks=True)
        return str(len(self.log))

    async def close(self) -> None:
        return None
