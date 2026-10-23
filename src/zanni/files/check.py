"""Check what `zanni <path>` was given: a Zanni file, or a folder holding one."""

from pathlib import Path

from pydantic import BaseModel

from zanni.files.errors import FileError, FileErrors
from zanni.files.kinds import detect
from zanni.files.loader import Loaded, load_file
from zanni.files.schemas import Script
from zanni.files.validation import validate

FOLDER_FILES = ("SCRIPT.md",)  # a folder is checked through the first of these it holds


def resolve(path: Path) -> Path:
    if not path.is_dir():
        return path
    for name in FOLDER_FILES:
        if (path / name).is_file():
            return path / name
    raise FileErrors([FileError(str(path), None, (), "is a folder with no Zanni file in it",
                                f"pass a file, or a folder holding one of: {', '.join(FOLDER_FILES)}")])


def check_body(loaded: Loaded) -> None:
    if not (loaded.body or "").strip():
        raise FileErrors([FileError(loaded.file, loaded.body_line, (), "has no prose after the frontmatter",
                                    "describe the acts and scenes for the director below the --- line")])


def check(path: str | Path) -> BaseModel:
    loaded = load_file(resolve(Path(path)))
    doc = validate(loaded, detect(loaded).model)
    if isinstance(doc, Script):
        check_body(loaded)
    return doc
