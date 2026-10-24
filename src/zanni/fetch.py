"""Fetch remote packages (roles and scripts) with the `git` command, into a cache (D37).

`host/owner/repo[/path]@version` resolves to a git tag on https://host/owner/repo.git (docs/spec/role-package.md,
"Versions"). Fetching takes one tag's commit, shallow, without submodules, and runs nothing. Zanni passes git no
credentials: git's own (SSH keys, a credential helper, `url.<base>.insteadOf`) do, and git never prompts.
"""

import difflib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from zanni.files.schemas import REMOTE_REF

VERSION = re.compile(r"^\d+\.\d+\.\d+$")
GIT_TIMEOUT = 300  # seconds for one git command; a fetch that hangs fails instead of waiting forever


class FetchError(Exception):
    """A package that can't be resolved or fetched, in plain words."""


@dataclass(frozen=True)
class Ref:
    """A remote package reference, split: the repository, the folder inside it, and the version."""

    text: str
    host: str
    owner: str
    repo: str
    path: str  # "" for a package at the repository's root
    version: str

    @property
    def url(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.repo}.git"

    def tags(self) -> list[str]:
        """The tags this version may be, in the spec's order."""
        own = [f"{self.path}/v{self.version}"] if self.path else []
        return [*own, f"v{self.version}", self.version]


def parse(ref: str) -> Ref:
    m = REMOTE_REF.match(ref)
    if not m:
        raise FetchError(f"{ref} is not a remote package reference; write host/owner/repo@1.0.0")
    parts = m["source"].split("/")
    if len(parts) < 3:
        raise FetchError(f"{ref} names no repository; write host/owner/repo@version, e.g. github.com/someone/tester@1.4.0")
    if not VERSION.match(m["version"]):
        raise FetchError(f"{ref}: {m['version']!r} is not an exact version; write major.minor.patch, e.g. @1.4.0")
    return Ref(ref, parts[0], parts[1], parts[2], "/".join(parts[3:]), m["version"])


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run git so that it never waits for a person: no password prompt, no SSH passphrase prompt (D37)."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": ""}
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    try:
        return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except FileNotFoundError:
        raise FetchError("git isn't installed; zanni fetches packages with the `git` command") from None
    except subprocess.TimeoutExpired:
        raise FetchError(f"git {args[0]} took longer than {GIT_TIMEOUT} s and was stopped") from None


def _failure(result: subprocess.CompletedProcess) -> str:
    lines = [ln for ln in result.stderr.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else f"git exited with {result.returncode}"


def remote_tags(url: str) -> dict[str, str]:
    """Every tag on the remote, and the commit it points to (an annotated tag is peeled to its commit)."""
    result = git("ls-remote", "--tags", url)
    if result.returncode != 0:
        raise FetchError(f"couldn't reach {url}: {_failure(result)}")
    tags: dict[str, str] = {}
    for line in result.stdout.splitlines():
        sha, _, name = line.partition("\t")
        name = name.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            tags[name[:-3]] = sha  # the peeled commit wins over the tag object
        else:
            tags.setdefault(name, sha)
    return tags


def resolve(ref: Ref) -> tuple[str, str]:
    """The tag and commit a reference resolves to; the first candidate tag that exists wins (role-package.md)."""
    tags = remote_tags(ref.url)
    found = [(t, tags[t]) for t in ref.tags() if t in tags]
    if not found:
        nearest = difflib.get_close_matches(ref.tags()[-1], [t.removeprefix("v") for t in tags], n=3, cutoff=0.5)
        hint = f"the nearest tags are: {', '.join(nearest)}" if nearest else (
            f"its tags are: {', '.join(sorted(tags)[:10])}" if tags else "it has no tags")
        raise FetchError(f"{ref.text}: {ref.url} has no tag {' or '.join(ref.tags())}; {hint}")
    commits = {c for _, c in found}
    if len(commits) > 1:
        raise FetchError(f"{ref.text}: the tags {' and '.join(t for t, _ in found)} point to different commits; "
                         "remove one of them, or ask the package's author which is right")
    return found[0]


def cache_root() -> Path:
    return Path.home() / ".zanni" / "packages"


def cached(ref: Ref, commit: str) -> Path:
    """Where a commit of this repository lives in the cache (it may not be there yet)."""
    return cache_root() / ref.host / ref.owner / ref.repo / commit


def folder(ref: Ref, commit: str) -> Path:
    """The package's own folder within a cached commit: the repository's root, or its subfolder."""
    return cached(ref, commit) / ref.path if ref.path else cached(ref, commit)


def fetch(ref: Ref, tag: str, commit: str) -> Path:
    """Fetch one tag, shallow, without submodules, into the cache, and check it is the expected commit.

    Returns the package's folder. A commit already in the cache isn't fetched again.
    """
    target = cached(ref, commit)
    if not target.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=".fetch-", dir=target.parent))
        try:
            for args in (("init", "--quiet"), ("fetch", "--quiet", "--depth", "1", "--no-tags", "--no-recurse-submodules",
                                              ref.url, f"refs/tags/{tag}")):
                result = git(*args, cwd=work)
                if result.returncode != 0:
                    raise FetchError(f"couldn't fetch {ref.text} ({tag}) from {ref.url}: {_failure(result)}")
            got = git("rev-parse", "FETCH_HEAD^{commit}", cwd=work).stdout.strip()
            if got != commit:
                raise FetchError(f"{ref.text}: the tag {tag} now points to {got}, and play.lock pins {commit}; "
                                 "someone moved the tag. Check with the package's author, then run "
                                 "zanni <play.yaml> --update to accept the new commit")
            result = git("-c", "advice.detachedHead=false", "checkout", "--quiet", "FETCH_HEAD", cwd=work)
            if result.returncode != 0:
                raise FetchError(f"couldn't check out {ref.text}: {_failure(result)}")
            shutil.rmtree(work / ".git")  # the cache holds the files only: nothing in it can run as a hook
            try:
                work.rename(target)
            except OSError:  # another process cached it first
                pass
        finally:
            shutil.rmtree(work, ignore_errors=True)
    package = folder(ref, commit)
    if not package.is_dir():
        raise FetchError(f"{ref.text}: the commit {commit[:12]} has no folder {ref.path}")
    return package


def fetch_latest(text: str) -> tuple[Path, str]:
    """Resolve a reference's tag and fetch it: for an actor's remote role, which has no lockfile. (folder, commit)"""
    ref = parse(text)
    tag, commit = resolve(ref)
    return fetch(ref, tag, commit), commit
