"""Check what `zanni <path>` was given: a Zanni file, or a folder holding one."""

import difflib
from pathlib import Path

from pydantic import BaseModel

from zanni.files.errors import FileError, FileErrors
from zanni.files.kinds import detect
from zanni.files.loader import Loaded, load_file
from zanni.files.schemas import REMOTE_REF, Lockfile, PlayFile, Script
from zanni.files.validation import validate

FOLDER_FILES = ("SCRIPT.md",)  # a folder is checked through the first of these it holds
LOCKFILE = "play.lock"


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


def load_script(loaded: Loaded, play: PlayFile, folder: Path) -> Script:
    """Load a play's local script; a missing one is reported on the play's `script:` line."""
    target = folder / play.script
    if not target.exists():
        raise FileErrors([FileError(loaded.file, loaded.line(("script",)), ("script",),
                                    f'"{play.script}" does not exist', "check the path, relative to the play file")])
    script_loaded = load_file(resolve(target))
    script = validate(script_loaded, Script)
    check_body(script_loaded)
    return script


def against_script(loaded: Loaded, play: PlayFile, script: Script) -> list[FileError]:
    """A play must cast the script's parts, within their seats, and use only the script's gates (D13)."""
    errors: list[FileError] = []
    for part, entry in play.cast.items():
        where = ("cast", part)
        if part not in script.parts:
            close = difflib.get_close_matches(part, list(script.parts), n=1)
            fix = f"did you mean `{close[0]}`?" if close else f"the script's parts are: {', '.join(script.parts)}"
            errors.append(FileError(loaded.file, loaded.line(where), where, "is not a part in the script", fix))
            continue
        limit = script.parts[part].seats
        if entry.seats and not (limit.min <= entry.seats.min and entry.seats.max <= limit.max):
            errors.append(FileError(loaded.file, loaded.line((*where, "seats")), (*where, "seats"),
                                    f"{entry.seats} is outside the script's {limit} for this part",
                                    f"use seats within {limit}, or leave `seats` out to use {limit}"))
    for part, spec in script.parts.items():
        if part not in play.cast and not spec.optional:
            errors.append(FileError(loaded.file, loaded.line(("cast",)), ("cast",),
                                    f"doesn't cast the script's part `{part}`", f"add `{part}:` with a role to cast"))
    for i, gate in enumerate(play.house_rules.gates):
        if gate not in script.gates:
            where = ("house_rules", "gates", i)
            errors.append(FileError(loaded.file, loaded.line(where), where, f'"{gate}" is not one of the script\'s gates',
                                    f"use one of: {', '.join(script.gates) or 'none (the script has no gates)'}"))
    return errors


def against_lockfile(loaded: Loaded, play: PlayFile, lock: Lockfile) -> list[FileError]:
    """If a play has a lockfile, every remote package it uses must be pinned in it (D18)."""
    errors: list[FileError] = []
    used = [(("script",), play.script, lock.script)] + [(("cast", part), e.role, lock.roles) for part, e in play.cast.items()]
    for where, ref, pins in used:
        if REMOTE_REF.match(ref) and ref not in pins:
            errors.append(FileError(loaded.file, loaded.line(where), where, f"{ref} is not pinned in {LOCKFILE}",
                                    f"add it to {LOCKFILE}, or remove {LOCKFILE} until it can be regenerated"))
    return errors


def check_play(loaded: Loaded, play: PlayFile) -> list[str]:
    folder = Path(loaded.file).parent
    errors: list[FileError] = []
    notes: list[str] = []
    if REMOTE_REF.match(play.script):
        notes.append("  script: remote, so the play wasn't checked against it (fetching scripts comes later)")
    else:
        errors += against_script(loaded, play, load_script(loaded, play, folder))
        notes.append("  script: checked; the play casts its parts within their seats, and uses its gates")
    if (folder / LOCKFILE).is_file():
        errors += against_lockfile(loaded, play, validate(load_file(folder / LOCKFILE), Lockfile))
        notes.append(f"  {LOCKFILE}: every remote package is pinned")
    if errors:
        raise FileErrors(sorted(errors, key=lambda e: e.line or 0))
    return notes


def check(path: str | Path) -> tuple[BaseModel, list[str]]:
    """Validate a file or folder. Returns the document and notes on the extra checks that ran."""
    loaded = load_file(resolve(Path(path)))
    doc = validate(loaded, detect(loaded).model)
    notes: list[str] = []
    if isinstance(doc, Script):
        check_body(loaded)
    if isinstance(doc, PlayFile):
        notes = check_play(loaded, doc)
    return doc, notes
