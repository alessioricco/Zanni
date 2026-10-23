from pathlib import Path

import pytest

from zanni.actor.roles import load_role, resolve_role_folder
from zanni.files.errors import FileErrors

EXAMPLES = Path(__file__).parents[1] / "examples"


def test_role_instructions_list_skills_and_bodies_load_on_demand():
    role = load_role(EXAMPLES / "roles/slug-tester")
    assert role.manifest.name == "slug-tester"
    assert role.instructions.startswith("# Slug tester")
    assert "- `write-test`: How to write one pytest test" in role.instructions
    assert role.skills["write-test"].startswith("# Write a test")


def test_remote_roles_are_refused_in_plain_words():
    with pytest.raises(FileErrors, match="fetching roles comes with milestone 4"):
        resolve_role_folder("github.com/someone/tester@1.4.0", Path("."))


def test_a_broken_role_is_refused_with_the_folder_checks(tmp_path):
    (tmp_path / "role.yaml").write_text("name: r\nversion: 1.0.0\nmission: m\n")
    with pytest.raises(FileErrors, match="AGENTS.md: is missing or empty"):
        load_role(tmp_path)
