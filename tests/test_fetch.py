"""Fetching packages with git, and play.lock (D37): bare repositories in tmp_path, reached through git's own
`url.<base>.insteadOf`, so `https://example.test/...` references are fetched over file:// with no network."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from zanni.actor.roles import resolve_role_folder
from zanni.director.packages import resolve_packages
from zanni.fetch import FetchError, cache_root, fetch_latest, git, parse, resolve
from zanni.files.errors import FileErrors
from zanni.files.hashing import package_hash
from zanni.files.schemas import PlayFile

EXAMPLES = Path(__file__).parents[1] / "examples"
SCRIPT = """---
name: kata
version: {version}
mission: Make the tests pass.
parts:
  coder: {{}}
verifiers:
  tests-pass: {{ description: every test passes, command: [{command}] }}
---

The **coder** makes the tests pass.
"""


def sh(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


class Remote:
    """A bare repository served as https://example.test/someone/<name>.git, through insteadOf."""

    def __init__(self, root: Path, name: str):
        self.work = root / "work" / name
        self.bare = root / "remotes" / "someone" / f"{name}.git"
        self.work.mkdir(parents=True)
        sh("git", "init", "-q", "-b", "main", cwd=self.work)
        self.bare.parent.mkdir(parents=True, exist_ok=True)
        sh("git", "init", "-q", "--bare", str(self.bare), cwd=root)

    def commit(self, files: dict[str, str], tag: str | None = None, *, force=False) -> str:
        for path, text in files.items():
            (self.work / path).parent.mkdir(parents=True, exist_ok=True)
            (self.work / path).write_text(text)
        sh("git", "add", "-A", cwd=self.work)
        sh("git", "-c", "user.name=t", "-c", "user.email=t@example.test", "commit", "-q", "-m", "c", cwd=self.work)
        if tag:
            sh("git", "tag", *(["-f"] if force else []), tag, cwd=self.work)
        sh("git", "push", "-q", *(["--force"] if force else []), str(self.bare), "main", "--tags", cwd=self.work)
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.work, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def remotes(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text(f'[url "file://{tmp_path}/remotes/"]\n\tinsteadOf = https://example.test/\n'
                         '[protocol "file"]\n\tallow = always\n')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return tmp_path


def role_files(version="1.0.0", mission="Write tests."):
    return {"role.yaml": f"name: tester\nversion: {version}\nmission: {mission}\n", "AGENTS.md": "# Tester\n"}


def test_a_reference_resolves_to_its_tag_and_is_fetched_into_the_cache(remotes):
    repo = Remote(remotes, "tester")
    commit = repo.commit(role_files(), "v1.0.0")
    where, got = fetch_latest("example.test/someone/tester@1.0.0")
    assert got == commit
    assert where == cache_root() / "example.test/someone/tester" / commit
    assert (where / "role.yaml").is_file() and not (where / ".git").exists()


def test_a_missing_tag_is_refused_with_the_nearest_ones(remotes):
    repo = Remote(remotes, "tester")
    repo.commit(role_files(), "v1.0.0")
    repo.commit(role_files("1.1.0"), "v1.1.0")
    with pytest.raises(FetchError, match=r"has no tag v1\.2\.0 or 1\.2\.0; the nearest tags are: 1\.1\.0"):
        resolve(parse("example.test/someone/tester@1.2.0"))


def test_a_package_in_a_subfolder_uses_its_own_tag_first_and_is_hashed_alone(remotes):
    repo = Remote(remotes, "roles")
    repo.commit({**{f"tester/{k}": v for k, v in role_files().items()}, "other/x.txt": "x"}, "tester/v1.0.0")
    tag, _ = resolve(parse("example.test/someone/roles/tester@1.0.0"))
    assert tag == "tester/v1.0.0"
    where, _ = fetch_latest("example.test/someone/roles/tester@1.0.0")
    assert where.name == "tester" and not (where / "x.txt").exists()
    alone = remotes / "alone"
    shutil.copytree(where, alone)
    assert package_hash(where) == package_hash(alone)


def test_two_candidate_tags_on_different_commits_are_refused(remotes):
    repo = Remote(remotes, "tester")
    repo.commit(role_files(), "v1.0.0")
    repo.commit(role_files(mission="Other."), "1.0.0")
    with pytest.raises(FetchError, match="v1.0.0 and 1.0.0 point to different commits"):
        resolve(parse("example.test/someone/tester@1.0.0"))


def test_only_exact_versions(remotes):
    with pytest.raises(FetchError, match="not an exact version"):
        parse("example.test/someone/tester@1.0")


def test_an_unreachable_remote_fails_in_plain_words(remotes, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(remotes / "closed-gitconfig"))
    (remotes / "closed-gitconfig").write_text('[url "http://127.0.0.1:9/"]\n\tinsteadOf = https://example.test/\n')
    with pytest.raises(FetchError, match="couldn't reach https://example.test/someone/tester.git"):
        resolve(parse("example.test/someone/tester@1.0.0"))


def test_git_never_waits_for_a_password(monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen.update(kwargs["env"])
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    git("ls-remote", "https://example.test/x.git")
    assert seen["GIT_TERMINAL_PROMPT"] == "0" and seen["GIT_ASKPASS"] == "" and "BatchMode=yes" in seen["GIT_SSH_COMMAND"]


def test_an_actors_remote_role_is_fetched(remotes):
    repo = Remote(remotes, "tester")
    repo.commit(role_files(), "v1.0.0")
    assert (resolve_role_folder("example.test/someone/tester@1.0.0", Path(".")) / "role.yaml").is_file()
    with pytest.raises(FileErrors, match="has no tag v1.0.0 or 1.0.0; it has no tags|couldn't reach"):
        resolve_role_folder("example.test/someone/missing@1.0.0", Path("."))


# play.lock

def play_folder(remotes, script_ref="example.test/someone/kata@1.0.0", role_ref="example.test/someone/tester@1.0.0"):
    folder = remotes / "play"
    folder.mkdir(exist_ok=True)
    (folder / "play.yaml").write_text(yaml.safe_dump({"name": "p", "script": script_ref, "stage": "./stage",
                                                      "cast": {"coder": role_ref}}))
    return folder / "play.yaml", PlayFile.model_validate(yaml.safe_load((folder / "play.yaml").read_text()))


@pytest.fixture
def published(remotes):
    kata, tester = Remote(remotes, "kata"), Remote(remotes, "tester")
    kata.commit({"SCRIPT.md": SCRIPT.format(version="1.0.0", command="pytest")}, "v1.0.0")
    tester.commit(role_files(), "v1.0.0")
    return remotes, kata, tester


def test_play_lock_is_written_once_and_pins_every_package(published):
    remotes, _, _ = published
    path, play = play_folder(remotes)
    said = []
    packages = resolve_packages(path, play, say=said.append)
    lock = yaml.safe_load((path.parent / "play.lock").read_text())
    assert packages.lock_written and said == [f"Wrote {path.parent / 'play.lock'}"]
    assert set(lock["script"]) == {"example.test/someone/kata@1.0.0"}
    pin = lock["roles"]["example.test/someone/tester@1.0.0"]
    assert len(pin["commit"]) == 40 and pin["hash"] == package_hash(packages.roles["example.test/someone/tester@1.0.0"].folder)
    before = (path.parent / "play.lock").read_text()
    again = resolve_packages(path, play, say=said.append)
    assert not again.lock_written and (path.parent / "play.lock").read_text() == before


def test_a_cached_pin_is_used_with_the_remote_gone(published):
    remotes, _, _ = published
    path, play = play_folder(remotes)
    resolve_packages(path, play, say=lambda _: None)
    shutil.rmtree(remotes / "remotes")
    packages = resolve_packages(path, play, say=lambda _: None)
    assert (packages.script.folder / "SCRIPT.md").is_file()


def test_a_moved_tag_is_refused_then_accepted_with_update_and_the_change_printed(published):
    remotes, kata, _ = published
    path, play = play_folder(remotes)
    first = resolve_packages(path, play, say=lambda _: None)
    shutil.rmtree(cache_root())  # so the run has to fetch, and sees the tag
    new = kata.commit({"SCRIPT.md": SCRIPT.format(version="1.0.0", command="npm, test")}, "v1.0.0", force=True)
    with pytest.raises(FetchError, match=rf"now points to {new}, and play.lock pins {first.script.pin.commit}"):
        resolve_packages(path, play, say=lambda _: None)
    said = []
    resolve_packages(path, play, update=True, say=said.append)
    assert said[0] == f"Updated {path.parent / 'play.lock'}"
    assert f"  example.test/someone/kata@1.0.0: {first.script.pin.commit[:12]} -> {new[:12]}" in said
    assert "  the old script isn't in the cache, so its verifier commands weren't compared" in said
    assert yaml.safe_load((path.parent / "play.lock").read_text())["script"]["example.test/someone/kata@1.0.0"]["commit"] == new


def test_update_prints_changed_verifier_commands(published):
    remotes, kata, _ = published
    path, play = play_folder(remotes)
    resolve_packages(path, play, say=lambda _: None)
    kata.commit({"SCRIPT.md": SCRIPT.format(version="1.0.0", command="npm, test")}, "v1.0.0", force=True)
    said = []
    resolve_packages(path, play, update=True, say=said.append)
    assert "  verifier tests-pass: pytest -> npm test" in said


def test_a_changed_file_is_caught_by_the_hash(published):
    remotes, _, _ = published
    path, play = play_folder(remotes)
    packages = resolve_packages(path, play, say=lambda _: None)
    (packages.roles["example.test/someone/tester@1.0.0"].folder / "AGENTS.md").write_text("# Tampered\n")
    with pytest.raises(FetchError, match="the fetched package's hash is .*, and play.lock pins"):
        resolve_packages(path, play, say=lambda _: None)


def test_a_local_package_that_changed_is_reported_not_refused(remotes):
    folder = remotes / "play"
    shutil.copytree(EXAMPLES / "roles/slug-tester", folder / "roles/tester")
    (folder / "kata").mkdir(parents=True)
    (folder / "kata/SCRIPT.md").write_text(SCRIPT.format(version="1.0.0", command="pytest"))
    path, play = play_folder(remotes, script_ref="./kata", role_ref="./roles/tester")
    resolve_packages(path, play, say=lambda _: None)
    assert "commit" not in yaml.safe_load((folder / "play.lock").read_text())["roles"]["./roles/tester"]
    (folder / "roles/tester/AGENTS.md").write_text("# Changed\n")
    said = []
    packages = resolve_packages(path, play, say=said.append)
    assert said == ["  ./roles/tester: changed since play.lock was written; using it as it is now (--update re-pins it)"]
    assert packages.roles["./roles/tester"].pin.hash == package_hash(folder / "roles/tester")
