"""The file decides what runs: tell actor files, play files and role manifests apart by their keys."""

import difflib
from dataclasses import dataclass

from pydantic import BaseModel

from zanni.files.errors import FileError, FileErrors
from zanni.files.loader import Loaded
from zanni.files.schemas import ActorFile, PlayFile, RoleManifest


@dataclass(frozen=True)
class Kind:
    name: str
    model: type[BaseModel]
    marker: frozenset[str]


KINDS = (
    Kind("actor file", ActorFile, frozenset({"role", "play"})),
    Kind("play file", PlayFile, frozenset({"cast"})),
    Kind("role manifest", RoleManifest, frozenset({"mission"})),
)


def detect(loaded: Loaded) -> Kind:
    keys = set(loaded.data)
    matches = [k for k in KINDS if k.marker <= keys]
    if len(matches) == 1:
        return matches[0]
    needs = "; ".join(f"{k.name}: {' and '.join(f'`{m}`' for m in sorted(k.marker))}" for k in KINDS)
    if not matches:
        markers = sorted({m for k in KINDS for m in k.marker})
        for key in sorted(keys - set(markers), key=str):
            close = difflib.get_close_matches(str(key), markers, n=1)
            if close:
                raise FileErrors([FileError(loaded.file, loaded.line((key,)), (key,), "is not a known field",
                                            f"did you mean `{close[0]}`?")])
        problem = "is not an actor file, a play file or a role manifest"
    else:
        problem = f"looks like more than one kind of file ({', '.join(k.name for k in matches)})"
    raise FileErrors([FileError(loaded.file, None, (), problem, f"each kind needs these fields: {needs}")])
