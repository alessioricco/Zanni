"""Check what `zanni <path>` was given: a Zanni file, or a folder holding one."""

import difflib
import json
import re
import stat
import subprocess
from pathlib import Path

from pydantic import BaseModel

from zanni.files.errors import FileError, FileErrors
from zanni.files.kinds import detect
from zanni.files.loader import Loaded, load_file, load_text
from zanni.files.schemas import (
    REMOTE_REF, ActorConfiguration, Lockfile, McpConfig, PlayFile, RoleManifest, Script, SkillFrontmatter,
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
    return [f"  folder: AGENTS.md; skills: {', '.join(skills) or 'none'}; mcp.json servers: {', '.join(servers) or 'none'}"]


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
        check_body(loaded)
    if isinstance(doc, PlayFile):
        notes = check_play(loaded, doc)
    if isinstance(doc, ActorConfiguration):
        check_credentials(loaded, doc)
    return doc, notes
