"""Load a role package into instructions and skills (D4). Uses zanni.files checks, so a broken role is refused
with the same plain-words errors as `zanni <role folder>`."""

from dataclasses import dataclass
from pathlib import Path

from zanni.files.check import check
from zanni.files.errors import FileError, FileErrors
from zanni.files.loader import load_file
from zanni.files.schemas import REMOTE_REF, RoleManifest


@dataclass(frozen=True)
class Role:
    folder: Path
    manifest: RoleManifest
    instructions: str  # AGENTS.md, then the skills' names and descriptions
    skills: dict[str, str]  # name -> body, loaded on demand through `load_skill`


def resolve_role_folder(ref: str, relative_to: Path) -> Path:
    """A local role folder, or a remote role fetched into the cache with git (D37)."""
    if REMOTE_REF.match(ref):
        from zanni.fetch import FetchError, fetch_latest

        try:
            return fetch_latest(ref)[0]
        except FetchError as e:
            raise FileErrors([FileError(ref, None, (), str(e).removeprefix(f"{ref}: "),
                                        "check the reference and that git can reach it, or use a local folder")]) from None
    return (relative_to / ref).resolve()


def load_role(folder: Path) -> Role:
    if not (folder / "role.yaml").is_file():
        raise FileErrors([FileError(str(folder), None, (), "is not a role folder (it has no role.yaml)",
                                    "point `role` at a folder holding role.yaml")])
    manifest, _ = check(folder)  # the whole-folder checks: AGENTS.md, skills, mcp.json, rehearsals
    assert isinstance(manifest, RoleManifest)
    skills: dict[str, str] = {}
    descriptions: list[str] = []
    for skill_md in sorted(folder.glob("skills/*/SKILL.md")):
        loaded = load_file(skill_md)
        skills[loaded.data["name"]] = (loaded.body or "").strip()
        descriptions.append(f"- `{loaded.data['name']}`: {loaded.data['description']}")
    instructions = (folder / "AGENTS.md").read_text().strip()
    if descriptions:
        instructions += "\n\n## Skills\n\nLoad a skill with the `load_skill` tool before using it.\n" + "\n".join(descriptions)
    return Role(folder, manifest, instructions, skills)
