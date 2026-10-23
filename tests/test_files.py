"""The CLI on the examples, which must validate, and on broken copies of them, which must not."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parent.parent / "examples"
ACTOR = EXAMPLES / "tester.yaml"
PLAY = EXAMPLES / "plays/habit-tracker/play.yaml"
ROLE = EXAMPLES / "roles/tester/role.yaml"
SCRIPT = EXAMPLES / "scripts/software-team/SCRIPT.md"
NEWSROOM = EXAMPLES / "scripts/newsroom"  # a folder holding SCRIPT.md
NEWSROOM_PLAY = EXAMPLES / "plays/newsroom/play.yaml"  # a play with a local script and a play.lock
REHEARSAL = EXAMPLES / "roles/slug-tester/rehearsals/smoke.yaml"
REHEARSAL_ACTOR = EXAMPLES / "slug-tester.yaml"  # an actor configuration whose play is a rehearsal


def zanni(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "zanni", str(path)], capture_output=True, text=True)


def broken(tmp_path: Path, example: Path, old: str, new: str) -> Path:
    text = example.read_text()
    assert old in text, f"{old!r} not in {example}"
    target = tmp_path / example.name
    target.write_text(text.replace(old, new, 1))
    return target


@pytest.mark.parametrize("example, first_line", [
    (ACTOR, "Actor configuration: would start 'tester-1', playing a role in a play."),
    (PLAY, "Play file: would start the director for the play 'habit-tracker'."),
    (ROLE, "Role manifest: the role 'tester' 1.4.0."),
    (SCRIPT, "Script: 'software-team' 1.0.0."),
    (NEWSROOM, "Script: 'newsroom' 0.1.0."),
    (NEWSROOM_PLAY, "Play file: would start the director for the play 'city-desk'."),
    (REHEARSAL, "Rehearsal: 'smoke', run with no director when an actor configuration's `play` points here."),
    (REHEARSAL_ACTOR, "Actor configuration: would start 'slug-tester-1', playing a role in a play."),
])
def test_examples_validate(example, first_line):
    result = zanni(example)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == first_line


def test_play_is_checked_against_its_local_script():
    out = zanni(NEWSROOM_PLAY).stdout
    assert "script: checked; the play casts its parts within their seats, and uses its gates" in out
    assert "play.lock: every remote package is pinned" in out


def test_play_with_remote_script_says_it_was_not_checked():
    assert "script: remote, so the play wasn't checked against it" in zanni(PLAY).stdout


def test_play_summary_shows_cast_and_house_rules():
    out = zanni(PLAY).stdout
    assert "coder: github.com/zanni-roles/coder@1.0.0, 1-4 seats, started here (local)" in out
    assert "house rules: budget $20.00; human gates: plan, release" in out


@pytest.mark.parametrize("example, old, new, expected", [
    (ACTOR, "tester@1.4.0", "tester",
     'line 5, role: "github.com/someone/tester" has no version; write it as github.com/someone/tester@1.0.0'),
    (ACTOR, "play:", "plya:", "line 6, plya: is not a known field; did you mean `play`?"),
    (PLAY, "seats: 1-4", "seats: 4-1", "line 9, cast.coder.seats: the range 4-1 goes down"),
    (PLAY, "host: local", "hots: local", "line 9, cast.coder.hots: is not a known field; did you mean `host`?"),
    (PLAY, "budget: 20.00", "budget: -1", "line 11, house_rules.budget: should be at least 0, not -1"),
    (PLAY, "director: wss://", "director: ftp://", "line 4, director: \"ftp://director.example.com\" is not a director address"),
    (PLAY, "  gates: [plan, release]", "  gates: [plan, release]\n  token: abc", "line 13, house_rules.token: looks like a secret"),
    (PLAY, "script: github.com/someone/habit-tracker@1.0.0", "script: github.com/someone/habit-tracker",
     'line 3, script: "github.com/someone/habit-tracker" has no version'),
    (PLAY, "script: github.com/someone/habit-tracker@1.0.0\n", "",
     "line 2, script: is required but missing; add a `script:` line"),
    (ROLE, "version: 1.4.0", "version: 1.4", "line 3, version: 1.4 was read as a number"),
    (ROLE, "mission:", "mision:", "line 4, mision: is not a known field; did you mean `mission`?"),
    (ROLE, "tools: true", "tools: maybe", 'line 5, model.needs.tools: should be true or false, not "maybe"'),
    (SCRIPT, "    seats: 1-8", "    seats: 8-1", "line 20, parts.coder.seats: the range 8-1 goes down"),
    (SCRIPT, "  max_rounds: 5", "  max_rounds: many", 'line 26, stop.max_rounds: should be a whole number, not "many"'),
])
def test_broken_copies_fail_in_plain_words(tmp_path, example, old, new, expected):
    result = zanni(broken(tmp_path, example, old, new))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "nothing was started" in result.stderr
    assert expected in result.stderr, result.stderr


def test_role_folder_checks_the_whole_package():
    result = zanni(ROLE.parent)
    assert result.returncode == 0, result.stderr
    assert "folder: AGENTS.md; skills: explore-app, write-test; mcp.json servers: browser, test-runner" in result.stdout


def test_role_folder_reports_a_tool_missing_from_mcp_json(tmp_path):
    shutil.copytree(ROLE.parent, tmp_path / "tester")
    (tmp_path / "tester/mcp.json").write_text('{"mcpServers": {"browser": {"command": "x"}}}')
    result = zanni(tmp_path / "tester")
    assert result.returncode == 2
    assert 'line 9, needs.tools[1]: "test-runner" is not a server in mcp.json; use one of mcp.json\'s servers (browser)' in result.stderr


def test_actor_pointing_at_a_rehearsal_says_it_runs_with_no_director():
    assert "play: the rehearsal 'smoke', 1 cue, run with no director" in zanni(REHEARSAL_ACTOR).stdout


def test_role_folder_lists_its_rehearsals():
    assert "rehearsals: smoke" in zanni(EXAMPLES / "roles/slug-tester").stdout


def test_missing_file(tmp_path):
    result = zanni(tmp_path / "nope.yaml")
    assert result.returncode == 2
    assert "nope.yaml: does not exist; check the path" in result.stderr


def test_local_role_folder_is_accepted(tmp_path):
    shutil.copy(PLAY, tmp_path / "play.yaml")
    target = broken(tmp_path, tmp_path / "play.yaml", "github.com/someone/tester@1.4.0", "roles/tester")
    assert zanni(target).returncode == 0
