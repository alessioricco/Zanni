"""A seat's workspace (D52): a local copy of the stage, filled at the start of each cue and sent back at its end.

The actor's engine works in the folder, through `zanni:workspace` (src/zanni/engine/workspace_server.py) or a tool the
actor brings (D53). What changed reaches the stage as ordinary writes and deletes over the seat's own connection, so
the director's permission layer checks every one of them (D43): a change outside the cue's paths is refused there,
never here. Only text files are sent, and none that the project's own `.gitignore` ignores, such as build output.
"""

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from zanni.actor.contract import Stage, StageError




def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class Synced:
    written: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)  # "<verb> <path>: <why>", as the stage refused it

    def __str__(self) -> str:
        bits = [f"{len(self.written)} written", f"{len(self.deleted)} deleted"]
        if self.refused:
            bits.append(f"{len(self.refused)} refused")
        return ", ".join(bits)


class Ignore:
    """The patterns of a `.gitignore` at the workspace's root, as git reads them, for the cases projects use: `#`
    comments, `!` to re-include, a trailing `/` for folders, a `/` inside to anchor at the root, `*`, `?` and `**`."""

    def __init__(self, text: str = ""):
        self.rules: list[tuple[re.Pattern, bool, bool]] = []  # (pattern, negated, folders only)
        for line in text.splitlines():
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            negated = line.startswith("!")
            line = line[1:] if negated else line.removeprefix("\\")
            folders = line.endswith("/")
            line = line.rstrip("/")
            anchored = "/" in line
            body = self._regex(line.lstrip("/"))
            self.rules.append((re.compile(("^" if anchored else "^(?:.*/)?") + body + "$"), negated, folders))

    @staticmethod
    def _regex(glob: str) -> str:
        out, i = "", 0
        while i < len(glob):
            if glob.startswith("**/", i):
                out, i = out + "(?:.*/)?", i + 3
            elif glob.startswith("**", i):
                out, i = out + ".*", i + 2
            elif glob[i] == "*":
                out, i = out + "[^/]*", i + 1
            elif glob[i] == "?":
                out, i = out + "[^/]", i + 1
            else:
                out, i = out + re.escape(glob[i]), i + 1
        return out

    def ignores(self, path: str) -> bool:
        """Whether a file is ignored, or sits in an ignored folder: the last matching rule wins, as in git."""
        parts = path.split("/")
        for depth in range(1, len(parts) + 1):
            prefix, is_folder = "/".join(parts[:depth]), depth < len(parts)
            verdict = None
            for pattern, negated, folders in self.rules:
                if (is_folder or not folders) and pattern.match(prefix):
                    verdict = not negated
            if verdict:
                return True
        return False


class Workspace:
    def __init__(self, folder: Path):
        self.folder = folder
        self.base: dict[str, str] = {}  # path -> digest, as filled at the start of the cue
        self.kept: set[str] = set()  # stage files that couldn't be copied (not text): never deleted by a sync

    async def fill(self, stage: Stage) -> None:
        """Empty the folder, and copy into it every stage file this seat may read."""
        if self.folder.exists():
            shutil.rmtree(self.folder)
        self.folder.mkdir(parents=True)
        self.base, self.kept = {}, set()
        for path in await stage.list(""):
            try:
                text = await stage.read(path)
            except StageError as e:
                if e.code in ("not-text", "not-found"):
                    self.kept.add(path)
                    continue
                raise
            target = self.folder / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
            self.base[path] = digest(text)

    def _ignore(self) -> Ignore:
        gitignore = self.folder / ".gitignore"
        return Ignore(gitignore.read_text() if gitignore.is_file() else "")

    def _current(self, ignore: Ignore) -> dict[str, str]:
        files = {}
        for p in sorted(self.folder.rglob("*")):
            rel = p.relative_to(self.folder).as_posix()
            if not p.is_file() or p.is_symlink() or ".git" in rel.split("/") or ignore.ignores(rel):
                continue
            try:
                files[rel] = p.read_text()
            except UnicodeDecodeError:
                continue  # only text reaches the stage (D43)
        return files

    async def sync(self, stage: Stage) -> Synced:
        """Send what changed since the fill: writes for new and changed files, deletes for removed ones. A refused
        operation is noted and the rest go on; a stage that stops answering raises, as any stage operation does."""
        synced = Synced()
        ignore = self._ignore()
        current = self._current(ignore)
        for path, text in current.items():
            if self.base.get(path) == digest(text):
                continue
            try:
                await stage.write(path, text)
                synced.written.append(path)
            except StageError as e:
                if e.code == "unavailable":
                    raise
                synced.refused.append(f"write {path}: {e.code}: {e}")
        for path in self.base:
            if path in current or path in self.kept or ignore.ignores(path):
                continue
            try:
                await stage.delete(path)
                synced.deleted.append(path)
            except StageError as e:
                if e.code == "unavailable":
                    raise
                synced.refused.append(f"delete {path}: {e.code}: {e}")
        return synced
