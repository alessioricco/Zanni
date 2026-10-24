"""A package's content hash, as play.lock pins it and an actor's card carries it (docs/spec/play.md, D18)."""

import hashlib
from pathlib import Path


def package_hash(folder: Path) -> str:
    """SHA-256 of a sha256sum-style listing of every file under `folder`, sorted by path, excluding .git/."""
    lines = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and ".git" not in p.relative_to(folder).parts):
        rel = path.relative_to(folder).as_posix()
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {rel}\n")
    return "sha256:" + hashlib.sha256("".join(lines).encode()).hexdigest()
