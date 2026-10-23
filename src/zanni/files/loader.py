"""Load a YAML file with the line of every field, so errors can point at it."""

from dataclasses import dataclass
from pathlib import Path as FsPath
from typing import Any

import yaml

from zanni.files.errors import FileError, FileErrors, Path


@dataclass
class Loaded:
    file: str
    data: Any
    lines: dict[Path, int]

    def line(self, path: Path) -> int | None:
        """The line of a field, or of its closest parent that has one."""
        for end in range(len(path), -1, -1):
            if path[:end] in self.lines:
                return self.lines[path[:end]]
        return None


def _walk(node: yaml.Node, path: Path, lines: dict[Path, int], errors: list[FileError], file: str) -> None:
    lines.setdefault(path, node.start_mark.line + 1)
    if isinstance(node, yaml.MappingNode):
        seen: set[str] = set()
        for key_node, value_node in node.value:
            key = key_node.value
            if key in seen:
                errors.append(FileError(file, key_node.start_mark.line + 1, (*path, key),
                                        "appears twice", "keep one of the two entries"))
            seen.add(key)
            lines[(*path, key)] = key_node.start_mark.line + 1
            _walk(value_node, (*path, key), lines, errors, file)
    elif isinstance(node, yaml.SequenceNode):
        for i, item in enumerate(node.value):
            _walk(item, (*path, i), lines, errors, file)


def load_text(text: str, file: str) -> Loaded:
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        data = yaml.safe_load(text)
    except yaml.MarkedYAMLError as e:
        mark = e.problem_mark or e.context_mark
        problem = (e.problem or "is not valid YAML").strip()
        raise FileErrors([FileError(file, mark.line + 1 if mark else None, (), f"is not valid YAML: {problem}",
                                    "check the indentation and the quotes on this line and the one before")])
    if node is None:
        raise FileErrors([FileError(file, None, (), "is empty", "see docs/files.md for what a Zanni file holds")])
    lines: dict[Path, int] = {}
    errors: list[FileError] = []
    _walk(node, (), lines, errors, file)
    if errors:
        raise FileErrors(errors)
    if not isinstance(data, dict):
        raise FileErrors([FileError(file, 1, (), "must be a set of `name: value` fields, not a single value or a list",
                                    "see docs/files.md")])
    return Loaded(file, data, lines)


def load_file(path: str | FsPath) -> Loaded:
    path = FsPath(path)
    try:
        text = path.read_text()
    except FileNotFoundError:
        raise FileErrors([FileError(str(path), None, (), "does not exist", "check the path")]) from None
    except (IsADirectoryError, UnicodeDecodeError):
        raise FileErrors([FileError(str(path), None, (), "is not a text file", "pass a .yaml file")]) from None
    return load_text(text, str(path))
