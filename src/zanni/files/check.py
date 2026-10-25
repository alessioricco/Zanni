"""Check what `zanni <path>` was given: a Zanni file, or a folder holding one."""

import difflib
import json
import re
import stat
import subprocess
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel

from zanni.files.errors import FileError, FileErrors
from zanni.files.kinds import detect
from zanni.files.loader import Loaded, load_file, load_text
from zanni.files.schemas import (
    REMOTE_REF, VERIFIER_ROLE, ActorConfiguration, Lockfile, McpConfig, PlayFile, Rehearsal, RoleManifest, Script,
    SkillFrontmatter,
)
from zanni.files.validation import is_secret_name, validate

FOLDER_FILES = ("role.yaml", "SCRIPT.md")  # a folder is checked through the first of these it holds
ENV_REF = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*(:-[^}]*)?\}$")
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


def check_script(loaded: Loaded, script: Script) -> None:
    """The prose is present, `stop.done_when` names only the script's verifiers (D35), a gate's `before` only
    its parts (D48), and every verifier's check files are in the script's folder (D55)."""
    check_body(loaded)
    errors = []
    seen = set()
    for i, gate in enumerate(script.gates):
        if gate.name in seen:
            where = ("gates", i)
            errors.append(FileError(loaded.file, loaded.line(where), where, f'the gate "{gate.name}" is listed twice',
                                    "list each gate once"))
        seen.add(gate.name)
        for j, part in enumerate(gate.before):
            if part not in script.parts:
                where = ("gates", i, "before", j)
                errors.append(FileError(loaded.file, loaded.line(where), where, f'"{part}" is not one of the script\'s parts',
                                        f"use one of: {', '.join(script.parts)}"))
    folder = Path(loaded.file).parent
    for name, verifier in script.verifiers.items():
        for i, path in enumerate(verifier.files):
            if not (folder / path).is_file():
                where = ("verifiers", name, "files", i)
                errors.append(FileError(loaded.file, loaded.line(where), where,
                                        f'"{path}" is not a file in the script\'s folder',
                                        f"add it to {folder}, or fix the path, relative to the script's folder"))
    for i, name in enumerate(script.stop.done_when):
        if name not in script.verifiers:
            where = ("stop", "done_when", i)
            errors.append(FileError(loaded.file, loaded.line(where), where, f'"{name}" is not one of the script\'s verifiers',
                                    f"use one of: {', '.join(script.verifiers) or 'none (add it under `verifiers`)'}"))
    if errors:
        raise FileErrors(errors)


class VerifierRun(NamedTuple):
    command: list[str] | None
    timeout: int
    source: str  # where the command came from: "play" or "script" (D35)
    runs_on: str | None = None  # a verifier seat's name; None: the director (D45)


def verifier_commands(play: PlayFile, script: Script) -> dict[str, VerifierRun]:
    """Each script verifier's command, timeout, where the command came from, and where it runs (D35, D45)."""
    out = {}
    for name, v in script.verifiers.items():
        own = play.verifiers.get(name)
        command, source = (own.command, "play") if own and own.command else (v.command, "script")
        timeout = own.timeout if own and own.timeout else v.timeout
        out[name] = VerifierRun(command, timeout, source, own.runs_on if own else None)
    return out


def load_script(loaded: Loaded, play: PlayFile, folder: Path) -> Script:
    """Load a play's local script; a missing one is reported on the play's `script:` line."""
    target = folder / play.script
    if not target.exists():
        raise FileErrors([FileError(loaded.file, loaded.line(("script",)), ("script",),
                                    f'"{play.script}" does not exist', "check the path, relative to the play file")])
    script_loaded = load_file(resolve(target))
    script = validate(script_loaded, Script)
    check_script(script_loaded, script)
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
    most = script.stop.max_rounds
    if play.house_rules.max_rounds and most and play.house_rules.max_rounds > most:
        where = ("house_rules", "max_rounds")
        errors.append(FileError(loaded.file, loaded.line(where), where,
                                f"{play.house_rules.max_rounds} is more than the script's stop.max_rounds, {most}",
                                f"use {most} or fewer; a play may lower the script's limit, never raise it"))
    for i, gate in enumerate(play.house_rules.gates):
        if gate not in script.gate_names:
            where = ("house_rules", "gates", i)
            errors.append(FileError(loaded.file, loaded.line(where), where, f'"{gate}" is not one of the script\'s gates',
                                    f"use one of: {', '.join(script.gate_names) or 'none (the script has no gates)'}"))
    for name in play.verifiers:
        if name not in script.verifiers:
            where = ("verifiers", name)
            errors.append(FileError(loaded.file, loaded.line(where), where, "is not one of the script's verifiers",
                                    f"a play only gives commands for the script's verifiers: "
                                    f"{', '.join(script.verifiers) or 'none'}"))
    for name, run in verifier_commands(play, script).items():
        if run.command is None:
            where = ("verifiers",) if play.verifiers else ("script",)
            errors.append(FileError(loaded.file, loaded.line(where), where,
                                    f"the script's verifier `{name}` has no command, and this play gives none",
                                    f"add it under the play's `verifiers`, e.g. {name}: {{ command: [pytest, -q] }}"))
    return errors


def describe_verifiers(play: PlayFile, script: Script) -> list[str]:
    """Every command the director may run, and where it came from: they run with the user's permissions (D35)."""
    lines = []
    for name, run in verifier_commands(play, script).items():
        if run.command is not None:
            where = f"on the verifier seat {run.runs_on}" if run.runs_on else "here"
            lines.append(f"    {name}: {' '.join(run.command)} (from the {run.source}; timeout {run.timeout} s; runs {where})")
    if not lines:
        return ["  verifiers: none"]
    return ["  verifiers, run on a snapshot of the stage, here with your permissions unless a verifier seat is named:",
            *lines]


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
        notes.append("  script: remote, so it is checked when the director fetches it (D37)")
    else:
        script = load_script(loaded, play, folder)
        errors += against_script(loaded, play, script)
        notes.append("  script: checked; the play casts its parts within their seats, and uses its gates")
        notes += describe_verifiers(play, script)
    if (folder / LOCKFILE).is_file():
        errors += against_lockfile(loaded, play, validate(load_file(folder / LOCKFILE), Lockfile))
        notes.append(f"  {LOCKFILE}: every remote package is pinned")
    if errors:
        raise FileErrors(sorted(errors, key=lambda e: e.line or 0))
    return notes


def load_mcp_json(path: Path) -> Loaded:
    """mcp.json is JSON; it is checked as JSON first, then parsed for line numbers (JSON is valid YAML)."""
    text = path.read_text()
    try:
        json.loads(text)
    except json.JSONDecodeError as e:
        raise FileErrors([FileError(str(path), e.lineno, (), f"is not valid JSON: {e.msg}",
                                    "check the commas and quotes on this line and the one before")]) from None
    return load_text(text, str(path))


def check_mcp(loaded: Loaded) -> McpConfig:
    config = validate(loaded, McpConfig, reject_secrets=False)
    errors = []
    for name, server in config.mcpServers.items():
        for section in ("env", "headers"):
            for key, value in getattr(server, section).items():
                if is_secret_name(key) and not ENV_REF.match(value):
                    where = ("mcpServers", name, section, key)
                    errors.append(FileError(loaded.file, loaded.line(where), where,
                                            "holds a literal secret, and a role is shared, so it never holds secrets",
                                            f"write ${{{key}}} and give the value in the actor configuration"))
    if errors:
        raise FileErrors(errors)
    return config


def check_rehearsal(loaded: Loaded, rehearsal: Rehearsal) -> list[str]:
    """A rehearsal's stage must be a folder next to it; it is copied fresh for every run (D26)."""
    stage = Path(loaded.file).parent / rehearsal.stage
    if not stage.is_dir():
        raise FileErrors([FileError(loaded.file, loaded.line(("stage",)), ("stage",),
                                    f'"{rehearsal.stage}" is not a folder', "point `stage` at a folder, relative to this file")])
    return []


def load_rehearsal(path: Path) -> tuple[Loaded, Rehearsal]:
    loaded = load_file(path)
    rehearsal = validate(loaded, Rehearsal)
    check_rehearsal(loaded, rehearsal)
    return loaded, rehearsal


def play_target(base: Path, play: str) -> tuple[str, str]:
    """What an actor configuration's `play` points at (D30): director, play-url, play, rehearsal or missing.

    Reads local files only; a URL is classified by its form, never fetched.
    """
    if "://" in play:
        if not re.match(r"^https?://\S+$", play):
            return "bad-url", play
        return ("play-url" if play.lower().endswith((".yaml", ".yml")) else "director"), play
    target = base / play
    if not target.is_file():
        return "missing", str(target)
    return ("rehearsal" if "cues" in load_file(target).data else "play"), str(target)


def same_role(ref: str, base: Path, cast_ref: str, play_folder: Path) -> bool:
    """Whether a configuration's role is the one a play casts: the same remote reference, or the same local folder."""
    if REMOTE_REF.match(ref) or REMOTE_REF.match(cast_ref):
        return ref == cast_ref
    return (base / ref).resolve() == (play_folder / cast_ref).resolve()


def check_director_seats(loaded: Loaded, director: ActorConfiguration, play_path: Path, play: PlayFile) -> list[str]:
    """A director configuration's local seats: one actor configuration per seat, for a part the play casts, playing
    that part's role. Only `name` and `role` are read from them, never their credentials (D36)."""
    base = Path(loaded.file).parent
    errors: list[FileError] = []
    names: dict[str, str] = {}
    for part, files in director.seats.items():
        if part not in play.cast:
            where = ("seats", part)
            errors.append(FileError(loaded.file, loaded.line(where), where, "is not a part the play casts",
                                    f"use one of: {', '.join(play.cast)}"))
            continue
        for i, file in enumerate(files):
            where = ("seats", part, i)
            target = base / file
            data = load_file(target).data if target.is_file() else None
            if not isinstance(data, dict) or "role" not in data or "play" not in data:
                errors.append(FileError(loaded.file, loaded.line(where), where,
                                        f'"{file}" is not an actor configuration',
                                        "point at an actor configuration file, relative to this one"))
                continue
            role, name = str(data["role"]), str(data.get("name") or Path(file).stem)
            if not same_role(role, target.parent, play.cast[part].role, play_path.parent):
                errors.append(FileError(loaded.file, loaded.line(where), where,
                                        f"{file} plays {role}, and the play casts {play.cast[part].role} as {part}",
                                        "list a configuration whose `role` is the part's role"))
            if name in names:
                errors.append(FileError(loaded.file, loaded.line(where), where,
                                        f"{file} has the name {name!r}, like {names[name]}",
                                        "give every local seat's configuration its own `name`"))
            names[name] = file
    for i, file in enumerate(director.verifier_seats.local):
        where = ("verifier_seats", "local", i)
        target = base / file
        data = load_file(target).data if target.is_file() else None
        if not isinstance(data, dict) or data.get("role") != VERIFIER_ROLE:
            errors.append(FileError(loaded.file, loaded.line(where), where,
                                    f'"{file}" is not a verifier seat\'s configuration',
                                    f"point at a configuration whose role is {VERIFIER_ROLE}, relative to this one"))
            continue
        name = str(data.get("name") or Path(file).stem)
        if name in names:
            errors.append(FileError(loaded.file, loaded.line(where), where,
                                    f"{file} has the name {name!r}, like {names[name]}",
                                    "give every seat's configuration its own `name`"))
        names[name] = file
    trusted = set(director.verifier_seats.remote) | {n for n, f in names.items() if f in director.verifier_seats.local}
    for name, verifier in play.verifiers.items():
        if verifier.runs_on and verifier.runs_on not in trusted:
            where = ("verifier_seats",) if director.verifier_seats.local or director.verifier_seats.remote else ("play",)
            errors.append(FileError(loaded.file, loaded.line(where), where,
                                    f"the play runs `{name}` on the verifier seat {verifier.runs_on!r}, which this "
                                    "configuration doesn't list",
                                    f"add it under verifier_seats: local (a configuration file) or remote (its name)"))
    for part, entry in play.cast.items():
        if entry.host == "local" and not director.seats.get(part):
            where = ("seats",) if director.seats else ("play",)
            errors.append(FileError(loaded.file, loaded.line(where), where,
                                    f"the play casts `{part}` with host: local, and no local seat is listed for it",
                                    f"add the actor configurations to start, e.g. seats: {{ {part}: [./{part}-1.yaml] }}"))
    if errors:
        raise FileErrors(errors)
    seats = [f"{part}: {', '.join(files)}" for part, files in director.seats.items()]
    lines = [f"  directs: the play '{play.name}' ({director.play})",
             f"  local seats: {'; '.join(seats) or 'none; every part waits for actors to join'}"]
    vs = director.verifier_seats
    if vs.local or vs.remote:
        lines.append(f"  verifier seats: {', '.join([*vs.local, *(n + ' (remote)' for n in vs.remote)])}")
    return lines


def check_director(loaded: Loaded, director: ActorConfiguration) -> list[str]:
    """A director configuration's `play` must be a local play file, which is checked too (D34)."""
    kind, where = play_target(Path(loaded.file).parent, director.play)
    if kind != "play":
        raise FileErrors([FileError(loaded.file, loaded.line(("play",)), ("play",),
                                    f'"{director.play}" is not a local play file',
                                    "a director runs a play on this machine; point `play` at its play.yaml")])
    play_loaded = load_file(Path(where))
    play = validate(play_loaded, PlayFile)
    notes = check_play(play_loaded, play)
    return check_director_seats(loaded, director, Path(where).resolve(), play) + notes


def check_bindings(loaded: Loaded, actor: ActorConfiguration) -> list[str]:
    """The tools an actor brings must be tools its role needs (D53); a remote role is checked when it is fetched."""
    if not actor.tools:
        return []
    if REMOTE_REF.match(actor.role):
        return ["  tools: checked against the role when the actor fetches it (D37)"]
    manifest = Path(loaded.file).parent / actor.role / "role.yaml"
    if not manifest.is_file():
        return []  # a missing role folder is reported when the actor starts
    needs = validate(load_file(manifest), RoleManifest).needs.tools
    errors = [FileError(loaded.file, loaded.line(("tools", name)), ("tools", name),
                        f'"{name}" is not a tool the role needs', "bind only tools in the role's needs.tools: "
                        f"{', '.join(needs) or 'none (this role needs no tools)'}")
              for name in actor.tools if name not in needs]
    if errors:
        raise FileErrors(errors)
    return ["  tools: each is one the role needs"]


def check_actor_play(loaded: Loaded, actor: ActorConfiguration) -> list[str]:
    """An actor configuration's `play`: a director, a play file, or a local rehearsal (D26, D30)."""
    if actor.is_director:
        return check_director(loaded, actor)
    kind, where = play_target(Path(loaded.file).parent, actor.play)
    if kind == "bad-url":
        raise FileErrors([FileError(loaded.file, loaded.line(("play",)), ("play",),
                                    f'"{actor.play}" is not an address zanni can join',
                                    "use an http:// or https:// URL, a play file or a rehearsal (D30)")])
    if kind == "director":
        return [f"  joins: the director at {where}"]
    if kind == "play-url":
        return [f"  joins: the director named in the play file {where}"]
    if kind != "rehearsal":
        return []
    if actor.is_verifier:
        raise FileErrors([FileError(loaded.file, loaded.line(("play",)), ("play",),
                                    "a verifier seat joins a director, not a rehearsal",
                                    "point `play` at the director's URL, or at its play file")])
    _, rehearsal = load_rehearsal(Path(where))
    cues = f"{len(rehearsal.cues)} cue{'s' if len(rehearsal.cues) > 1 else ''}"
    return [f"  runs: the rehearsal '{rehearsal.rehearsal}', {cues}, with a director started for it here"]


def check_role_folder(folder: Path, loaded: Loaded, role: RoleManifest) -> list[str]:
    """A role folder: role.yaml, AGENTS.md, skills in SKILL.md format, and mcp.json for the tools it needs."""
    errors: list[FileError] = []
    agents = folder / "AGENTS.md"
    if not agents.is_file() or not agents.read_text().strip():
        errors.append(FileError(str(agents), None, (), "is missing or empty",
                                "write the role's character and instructions in AGENTS.md"))
    skills = []
    for skill_dir in sorted(p for p in (folder / "skills").glob("*") if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            errors.append(FileError(str(skill_dir), None, (), "is a skill folder with no SKILL.md",
                                    "add SKILL.md, or remove the folder"))
            continue
        try:
            skill_loaded = load_file(skill_md)
            if skill_loaded.body is None:
                raise FileErrors([FileError(str(skill_md), 1, (), "has no frontmatter",
                                            "start it with --- lines holding `name` and `description`")])
            skill = validate(skill_loaded, SkillFrontmatter)
            if skill.name != skill_dir.name:
                errors.append(FileError(str(skill_md), skill_loaded.line(("name",)), ("name",),
                                        f'"{skill.name}" doesn\'t match its folder "{skill_dir.name}"',
                                        "rename the folder or the skill so they match"))
            skills.append(skill.name)
        except FileErrors as e:
            errors += e.errors
    rehearsals = []
    for path in sorted((folder / "rehearsals").glob("*.yaml")):
        try:
            rehearsals.append(load_rehearsal(path)[1].rehearsal)
        except FileErrors as e:
            errors += e.errors
    servers: list[str] = []
    mcp = folder / "mcp.json"
    if mcp.is_file():
        try:
            servers = list(check_mcp(load_mcp_json(mcp)).mcpServers)
        except FileErrors as e:
            errors += e.errors
    for i, tool in enumerate(role.needs.tools):
        if tool not in servers:
            where = ("needs", "tools", i)
            fix = (f"add a `{tool}` server to mcp.json" if not servers
                   else f"use one of mcp.json's servers ({', '.join(servers)}), or add `{tool}` to it")
            errors.append(FileError(loaded.file, loaded.line(where), where, f'"{tool}" is not a server in mcp.json', fix))
    if errors:
        raise FileErrors(errors)
    return [f"  folder: AGENTS.md; skills: {', '.join(skills) or 'none'}; mcp.json servers: {', '.join(servers) or 'none'}"
            + (f"; rehearsals: {', '.join(rehearsals)}" if rehearsals else "")]


def git_tracks(path: Path) -> bool:
    """Whether git tracks this file. False when git isn't installed or the file isn't in a repository."""
    try:
        result = subprocess.run(["git", "ls-files", "--error-unmatch", path.name], cwd=path.parent,
                                capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def check_credentials(loaded: Loaded, actor: ActorConfiguration) -> None:
    """A configuration storing credentials must be private to its owner and kept out of git (D15)."""
    if not actor.stored_credentials():
        return
    path = Path(loaded.file)
    line = loaded.line(("credentials",))
    errors = []
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        errors.append(FileError(loaded.file, line, ("credentials",),
                                f"holds credentials, but other users can read this file (mode {mode:o})",
                                f"run: chmod 600 {path}"))
    if git_tracks(path):
        errors.append(FileError(loaded.file, line, ("credentials",), "holds credentials, but git tracks this file",
                                f"remove it from git (git rm --cached {path.name}) and add it to .gitignore, "
                                "or use ${VAR} references instead of values"))
    if errors:
        raise FileErrors(errors)


def check(path: str | Path) -> tuple[BaseModel, list[str]]:
    """Validate a file or folder. Returns the document and notes on the extra checks that ran."""
    target = resolve(Path(path))
    loaded = load_file(target)
    doc = validate(loaded, detect(loaded).model)
    notes: list[str] = []
    if isinstance(doc, RoleManifest):
        if Path(path).is_dir():
            notes = check_role_folder(Path(path), loaded, doc)
        else:
            notes = ["  (pass the role's folder to also check AGENTS.md, skills and mcp.json)"]
    if isinstance(doc, Script):
        check_script(loaded, doc)
    if isinstance(doc, PlayFile):
        notes = check_play(loaded, doc)
    if isinstance(doc, ActorConfiguration):
        check_credentials(loaded, doc)
        notes = check_bindings(loaded, doc) + check_actor_play(loaded, doc)
    if isinstance(doc, Rehearsal):
        check_rehearsal(loaded, doc)
    return doc, notes
