"""The file decides what runs: tell actor configurations, play files and role manifests apart by their keys."""

import difflib
from dataclasses import dataclass

from pydantic import BaseModel

from zanni.files.errors import FileError, FileErrors
from zanni.files.loader import Loaded
from zanni.files.schemas import ActorConfiguration, Lockfile, PlayFile, Rehearsal, RoleManifest, Script


@dataclass(frozen=True)
class Kind:
    name: str
    model: type[BaseModel]
    marker: frozenset[str]
    markdown: bool = False  # a Markdown file with frontmatter, rather than plain YAML
    excludes: frozenset[str] = frozenset()  # keys that mean it is another kind


KINDS = (
    Kind("actor configuration", ActorConfiguration, frozenset({"role", "play"})),
    Kind("play file", PlayFile, frozenset({"cast"})),
    Kind("role manifest", RoleManifest, frozenset({"mission"}), excludes=frozenset({"parts"})),
    Kind("script", Script, frozenset({"parts"}), markdown=True),
    Kind("lockfile", Lockfile, frozenset({"lock_version"})),
    Kind("rehearsal", Rehearsal, frozenset({"cues"})),
)


def detect(loaded: Loaded) -> Kind:
    keys = set(loaded.data)
    matches = [k for k in KINDS if k.marker <= keys and not k.excludes & keys]
    if len(matches) == 1:
        kind = matches[0]
        if kind.markdown and loaded.body is None:
            raise FileErrors([FileError(loaded.file, None, (), f"looks like a {kind.name}, but a {kind.name} is a Markdown file",
                                        "put these fields between --- lines at the top of a .md file, then the prose")])
        if not kind.markdown and loaded.body is not None:
            raise FileErrors([FileError(loaded.file, None, (), f"looks like a {kind.name}, but a {kind.name} is a YAML file",
                                        "remove the --- lines and the prose")])
        return kind
    needs = "; ".join(f"{k.name}: {' and '.join(f'`{m}`' for m in sorted(k.marker))}" for k in KINDS)
    if not matches:
        markers = sorted({m for k in KINDS for m in k.marker})
        for key in sorted(keys - set(markers), key=str):
            close = difflib.get_close_matches(str(key), markers, n=1)
            if close:
                raise FileErrors([FileError(loaded.file, loaded.line((key,)), (key,), "is not a known field",
                                            f"did you mean `{close[0]}`?")])
        problem = "is not an actor configuration, a play file, a role manifest, a script, a lockfile or a rehearsal"
    else:
        problem = f"looks like more than one kind of file ({', '.join(k.name for k in matches)})"
    raise FileErrors([FileError(loaded.file, None, (), problem, f"each kind needs these fields: {needs}")])
