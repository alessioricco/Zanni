"""A play's packages: its script and the role cast into each part, resolved, fetched and pinned in play.lock (D18, D37).

A run never rewrites an existing play.lock: only `--update` does. A pinned commit already in the cache is used
without touching the network.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from zanni.fetch import FetchError, cached, fetch, folder, parse, resolve
from zanni.files.check import LOCKFILE, resolve as resolve_file, verifier_commands
from zanni.files.errors import FileErrors
from zanni.files.hashing import package_hash
from zanni.files.loader import load_file
from zanni.files.schemas import REMOTE_REF, Lockfile, Pin, PlayFile, Script
from zanni.files.validation import validate


@dataclass
class Package:
    ref: str
    folder: Path  # the package's own folder (for a script, the folder holding SCRIPT.md)
    pin: Pin


@dataclass
class Packages:
    script: Package
    roles: dict[str, Package]  # by reference
    notes: list[str] = field(default_factory=list)
    lock_written: bool = False


def script_folder(path: Path) -> Path:
    """A local script reference may name SCRIPT.md or its folder; the package is the folder."""
    return path if path.is_dir() else path.parent


def _remote(ref: str, pin: Pin | None, update: bool) -> Package:
    r = parse(ref)
    if update:
        pin = None
    if pin is not None and cached(r, pin.commit).is_dir():
        where = folder(r, pin.commit)  # offline: the pinned commit is already here
    else:
        tag, commit = resolve(r)
        if pin is not None and commit != pin.commit:
            raise FetchError(f"{ref}: its tag {tag} now points to {commit}, and {LOCKFILE} pins {pin.commit}; someone "
                             "moved the tag. Check with the package's author, then run --update to accept the new commit")
        where = fetch(r, tag, commit)
        if pin is None:
            return Package(ref, where, Pin(commit=commit, hash=package_hash(where)))
    current = package_hash(where)
    if current != pin.hash:
        raise FetchError(f"{ref}: the fetched package's hash is {current}, and {LOCKFILE} pins {pin.hash}; it changed "
                         "since it was pinned. Check it, then run --update to re-pin it")
    return Package(ref, where, pin)


def _local(ref: str, where: Path, pin: Pin | None, notes: list[str]) -> Package:
    current = package_hash(where)
    if pin is not None and pin.hash != current:
        notes.append(f"  {ref}: changed since {LOCKFILE} was written; using it as it is now (--update re-pins it)")
    return Package(ref, where, Pin(hash=current))


def _get(ref: str, base: Path, pins: dict[str, Pin], update: bool, notes: list[str], is_script: bool) -> Package:
    if REMOTE_REF.match(ref):
        return _remote(ref, pins.get(ref), update)
    where = (base / ref).resolve()
    return _local(ref, script_folder(where) if is_script else where, pins.get(ref), notes)


def _lock_text(packages: Packages) -> str:
    def pin(p: Package) -> dict:
        return {"commit": p.pin.commit, "hash": p.pin.hash} if p.pin.commit else {"hash": p.pin.hash}

    doc = {"lock_version": 1, "script": {packages.script.ref: pin(packages.script)},
           "roles": {ref: pin(p) for ref, p in packages.roles.items()}}
    return ("# Written by zanni (D18, D37): the play's packages, pinned. Rewritten only by --update.\n"
            + yaml.safe_dump(doc, sort_keys=False))


def load_script(package: Package) -> Script:
    loaded = load_file(resolve_file(package.folder))
    return validate(loaded, Script)


def resolve_packages(play_path: Path, play: PlayFile, *, update: bool = False,
                     say: Callable[[str], None] = print) -> Packages:
    """Resolve, fetch and check every package the play uses, writing play.lock when it is missing (or on --update).

    Raises FetchError or FileErrors in plain words; nothing has started when it does.
    """
    base = play_path.parent
    lock_path = base / LOCKFILE
    old: Lockfile | None = validate(load_file(lock_path), Lockfile) if lock_path.is_file() else None
    pins = {**old.script, **old.roles} if old else {}
    notes: list[str] = []
    script = _get(play.script, base, pins, update, notes, is_script=True)
    roles: dict[str, Package] = {}
    for entry in play.cast.values():
        if entry.role not in roles:
            roles[entry.role] = _get(entry.role, base, pins, update, notes, is_script=False)
    packages = Packages(script, roles, notes)
    if old is None or update:
        if update and old is not None:
            packages.notes += _changes(old, packages, play)
        lock_path.write_text(_lock_text(packages))
        packages.lock_written = True
        say(f"{'Updated' if old else 'Wrote'} {lock_path}")
    for note in packages.notes:
        say(note)
    return packages


def _changes(old: Lockfile, new: Packages, play: PlayFile) -> list[str]:
    """What --update changed: the commits, and the verifier commands that changed (D35, D37)."""
    lines = []
    before = {**old.script, **old.roles}
    for p in [new.script, *new.roles.values()]:
        was = before.get(p.ref)
        if was is None:
            lines.append(f"  {p.ref}: pinned for the first time")
        elif was.commit != p.pin.commit:
            lines.append(f"  {p.ref}: {was.commit[:12] if was.commit else 'local'} -> {p.pin.commit[:12]}")
        elif was.hash != p.pin.hash:
            lines.append(f"  {p.ref}: its content changed ({was.hash[:19]}… -> {p.pin.hash[:19]}…)")
    old_script_pin = old.script.get(play.script)
    if old_script_pin and old_script_pin.commit and old_script_pin.commit != new.script.pin.commit:
        old_folder = folder(parse(play.script), old_script_pin.commit)
        if old_folder.is_dir():
            try:
                lines += _verifier_changes(load_script(Package(play.script, old_folder, old_script_pin)),
                                           load_script(new.script), play)
            except FileErrors:
                lines.append("  the old script can't be read, so its verifier commands weren't compared")
        else:
            lines.append("  the old script isn't in the cache, so its verifier commands weren't compared")
    return lines or ["  nothing changed"]


def _verifier_changes(before: Script, after: Script, play: PlayFile) -> list[str]:
    was, now = verifier_commands(play, before), verifier_commands(play, after)
    lines = []
    for name in sorted(set(was) | set(now)):
        a, b = was.get(name, (None, 0, ""))[0], now.get(name, (None, 0, ""))[0]
        if a != b:
            show = lambda c: " ".join(c) if c else "none"  # noqa: E731
            lines.append(f"  verifier {name}: {show(a)} -> {show(b)}")
    return lines
