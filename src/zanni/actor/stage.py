"""The `folder` stage backend (docs/spec/stage.md): a folder, the five operations, and one seat's permissions.

Enforcement lives here, in the stage, never in the prompt (golden rule 5). The director, and for now the
rehearsal runner, keeps the append-only record of changes; change markers are positions in it.
"""

from pathlib import Path

from zanni.actor.contract import StageError
from zanni.files.schemas import covers


def check_path(path: str) -> str:
    """A stage path: relative, with `/`, and no `..`, empty segments or backslashes."""
    if not path or path.startswith("/") or "\\" in path:
        raise StageError("invalid-path", f"{path!r} is not a stage path; write it relative to the stage root, e.g. tests/a.py")
    segments = path.rstrip("/").split("/")  # raw segments: PurePosixPath would quietly drop a "./"
    if any(seg in ("", "..", ".") for seg in segments):
        raise StageError("invalid-path", f"{path!r} is not a stage path; it may not contain '..', '.' or empty segments")
    return path


class FolderStage:
    """One seat's view of a folder stage. Seats of one play share `record`, so markers mean the same to all."""

    def __init__(self, root: Path, read: list[str], write: list[str], record: list[tuple[str, str]] | None = None):
        self.root = root.resolve()
        self.read_rules = list(read) + list(write)  # writing implies reading
        self.write_rules = list(write)
        self.record: list[tuple[str, str]] = [] if record is None else record  # (path, change), append-only

    def seat(self, read: list[str], write: list[str]) -> "FolderStage":
        """The same stage and record, with another seat's permissions."""
        return FolderStage(self.root, read, write, self.record)

    def _may(self, rules: list[str], path: str) -> bool:
        return any(covers(rule, path) for rule in rules)

    def _target(self, path: str, rules: list[str], verb: str) -> Path:
        check_path(path)
        if not self._may(rules, path):
            raise StageError("not-permitted", f"this seat may not {verb} {path}; it may {verb}: "
                                              f"{', '.join(rules) or 'nothing'}")
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):  # a symlink pointing out of the stage
            raise StageError("invalid-path", f"{path} leads outside the stage")
        return target

    def _marker(self) -> str:
        return str(len(self.record))

    def read(self, path: str) -> str:
        target = self._target(path, self.read_rules, "read")
        if not target.is_file():
            raise StageError("not-found", f"{path} doesn't exist on the stage")
        return target.read_text()

    def write(self, path: str, content: str) -> str:
        target = self._target(path, self.write_rules, "write")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        self.record.append((path, "written"))
        return self._marker()

    def list(self, path: str = "") -> list[str]:
        if path:
            check_path(path.rstrip("/"))
        folder = (self.root / path).resolve()
        if not folder.is_dir() or not folder.is_relative_to(self.root):
            raise StageError("not-found", f"{path or 'the stage root'} is not a folder on the stage")
        found = []
        for p in sorted(folder.rglob("*")):
            rel = p.relative_to(self.root).as_posix()
            if p.is_file() and self._may(self.read_rules, rel):
                found.append(rel)
        return found

    def delete(self, path: str) -> str:
        target = self._target(path, self.write_rules, "delete")
        if not target.is_file():
            raise StageError("not-found", f"{path} doesn't exist on the stage")
        target.unlink()
        self.record.append((path, "deleted"))
        return self._marker()

    def changes(self, since: str | None = None) -> tuple[list[tuple[str, str]], str]:
        start = 0
        if since is not None:
            if not since.isdigit() or int(since) > len(self.record):
                raise StageError("unknown-marker", f"{since!r} is not a change marker this stage gave")
            start = int(since)
        visible = [(p, c) for p, c in self.record[start:] if self._may(self.read_rules, p)]
        return visible, self._marker()
