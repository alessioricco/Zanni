"""Errors in plain words: the file, the line, the field, what is wrong and what to change."""

from dataclasses import dataclass

Path = tuple[str | int, ...]


def render_path(path: Path) -> str:
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


@dataclass(frozen=True)
class FileError:
    file: str
    line: int | None
    path: Path
    problem: str
    fix: str = ""

    def __str__(self) -> str:
        where = ", ".join(x for x in (self.file, f"line {self.line}" if self.line else "") if x)
        field = f"{render_path(self.path)}: " if self.path else ""
        return f"{where}, {field}{self.problem}" + (f"; {self.fix}" if self.fix else "")


class FileErrors(Exception):
    """One or more problems in a file. Each problem is reported; nothing runs until all are fixed."""

    def __init__(self, errors: list[FileError]):
        self.errors = errors
        super().__init__("\n".join(str(e) for e in errors))
