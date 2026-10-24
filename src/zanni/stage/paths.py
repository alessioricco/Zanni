"""Stage paths (docs/spec/stage.md, "Paths"): relative, written with `/`, never leaving the stage."""

from zanni.stage.errors import StageError


def check_path(path: str) -> str:
    """A stage path: relative, with `/`, and no `..`, empty segments or backslashes."""
    if not path or path.startswith("/") or "\\" in path:
        raise StageError("invalid-path", f"{path!r} is not a stage path; write it relative to the stage root, e.g. tests/a.py")
    segments = path.rstrip("/").split("/")  # raw segments: PurePosixPath would quietly drop a "./"
    if any(seg in ("", "..", ".") for seg in segments):
        raise StageError("invalid-path", f"{path!r} is not a stage path; it may not contain '..', '.' or empty segments")
    return path
