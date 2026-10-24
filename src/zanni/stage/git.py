"""The `git` backend (D46): a clone on the director's machine, one branch per run, one commit per write.

Storage only (D43): the layer above decides who may write what. The seat and the cue reach git as a commit's author
and message. The director pushes the run's branch, and only it; git's own authentication does the rest, and git never
prompts (GIT_TERMINAL_PROMPT=0, SSH BatchMode), as when fetching packages (D37). Zanni stores no git credential.
"""

from __future__ import annotations  # `list` is a method name below; Python < 3.14 evaluates annotations eagerly

import asyncio
import io
import os
import re
import subprocess
import tarfile
from pathlib import Path

from zanni.stage.errors import StageError

GIT_TIMEOUT = 300  # seconds for one git command, such as a clone or a push
DIRECTOR = ("zanni director", "director@zanni.invalid")


def _env(author: str | None = None) -> dict[str, str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": "",
           "GIT_COMMITTER_NAME": DIRECTOR[0], "GIT_COMMITTER_EMAIL": DIRECTOR[1],
           "GIT_AUTHOR_NAME": author or DIRECTOR[0],
           "GIT_AUTHOR_EMAIL": f"{re.sub(r'[^A-Za-z0-9._-]+', '-', author)}@zanni.invalid" if author else DIRECTOR[1]}
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return env


def run_git(*args: str, cwd: Path | None = None, author: str | None = None,
            text: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=cwd, env=_env(author), capture_output=True, text=text,
                              timeout=GIT_TIMEOUT)
    except FileNotFoundError:
        raise StageError("unavailable", "git isn't installed; a git stage needs the `git` command") from None
    except subprocess.TimeoutExpired:
        raise StageError("unavailable", f"git {args[0]} took longer than {GIT_TIMEOUT} s") from None


def failure(result: subprocess.CompletedProcess) -> str:
    err = result.stderr if isinstance(result.stderr, str) else result.stderr.decode(errors="replace")
    lines = [ln for ln in err.strip().splitlines() if ln.strip()]
    return lines[-1] if lines else f"git exited with {result.returncode}"


class CannotClone(Exception):
    """The stage's repository couldn't be cloned, or its branch doesn't exist: the play can't start (exit 2)."""


class GitBackend:
    kind = "git"

    def __init__(self, clone: Path, branch: str, run_branch: str, url: str):
        self.root, self.branch, self.run_branch, self.url = clone, branch, run_branch, url

    @classmethod
    def open(cls, url: str, branch: str, clone: Path, run_branch: str) -> GitBackend:
        """Clone `url` into `clone`, and make the run's branch from the tip of `branch`."""
        clone.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = run_git("clone", "--quiet", "--no-recurse-submodules", "--branch", branch, url, str(clone))
        except StageError as e:
            raise CannotClone(str(e)) from None
        if result.returncode != 0:
            raise CannotClone(f"couldn't clone {url} (branch {branch}): {failure(result)}")
        result = run_git("checkout", "--quiet", "-b", run_branch, cwd=clone)
        if result.returncode != 0:
            raise CannotClone(f"couldn't make the run's branch {run_branch}: {failure(result)}")
        return cls(clone, branch, run_branch, url)

    async def _git(self, *args: str, author: str | None = None, text: bool = True) -> subprocess.CompletedProcess:
        return await asyncio.to_thread(run_git, *args, cwd=self.root, author=author, text=text)

    def _file(self, path: str) -> Path:
        if path == ".git" or path.startswith(".git/"):
            raise StageError("invalid-path", f"{path} is git's own folder, not part of the stage")
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root.resolve()):
            raise StageError("invalid-path", f"{path} leads outside the stage")
        return target

    async def head(self) -> str:
        return (await self._git("rev-parse", "HEAD")).stdout.strip()

    async def read(self, path: str) -> str:
        target = self._file(path)
        if not target.is_file():
            raise StageError("not-found", f"{path} doesn't exist on the stage")
        try:
            return target.read_text()
        except UnicodeDecodeError:
            raise StageError("not-text", f"{path} isn't a text file; the stage carries text only") from None

    async def write(self, path: str, content: str, *, author: str | None = None, note: str | None = None) -> str:
        target = self._file(path)
        if (await self._git("check-ignore", "--quiet", "--no-index", "--", path)).returncode == 0:
            raise StageError("invalid-path", f"{path} is ignored by the repository's .gitignore, so it would never be "
                                             "committed; write it somewhere else")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return await self._commit(path, author, note or f"write {path}", ("add", "--", path))

    async def delete(self, path: str, *, author: str | None = None, note: str | None = None) -> str:
        target = self._file(path)
        if not target.is_file():
            raise StageError("not-found", f"{path} doesn't exist on the stage")
        return await self._commit(path, author, note or f"delete {path}", ("rm", "--quiet", "--", path))

    async def _commit(self, path: str, author: str | None, message: str, stage_args: tuple[str, ...]) -> str:
        result = await self._git(*stage_args)
        if result.returncode != 0:
            raise StageError("unavailable", f"git couldn't record {path}: {failure(result)}")
        result = await self._git("commit", "--quiet", "--allow-empty", "--no-verify", "-m", message, author=author)
        if result.returncode != 0:
            raise StageError("unavailable", f"git couldn't commit {path}: {failure(result)}")
        return await self.head()

    async def list(self, folder: str = "") -> list[str]:
        if folder and not self._file(folder).is_dir():
            raise StageError("not-found", f"{folder} is not a folder on the stage")
        files = (await self._git("ls-files", "-z", "--", folder or ".")).stdout.split("\0")
        return sorted(f for f in files if f)

    async def changes(self, since: str | None = None) -> tuple[list[tuple[str, str]], str]:
        head = await self.head()
        args = ("diff", "--name-status", "--no-renames", f"{since}..HEAD") if since else ("ls-files",)
        result = await self._git(*args)
        if result.returncode != 0:
            raise StageError("unknown-marker", f"{since!r} is not a commit on the run's branch")
        out = []
        for line in result.stdout.splitlines():
            status, _, path = line.partition("\t") if since else ("A", "", line)
            out.append((path, "deleted" if status.startswith("D") else "written"))
        return out, head

    async def snapshot(self, into: Path) -> str:
        """The latest commit, extracted: exactly what was committed, nothing half-written."""
        result = await self._git("archive", "--format=tar", "HEAD", text=False)
        if result.returncode != 0:
            raise StageError("unavailable", f"git couldn't export the stage: {failure(result)}")
        with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
            tar.extractall(into, filter="data")
        return await self.head()

    async def push(self) -> tuple[bool, str]:
        """Push the run's branch, and only it, to the stage's remote (D46). (ok, detail)."""
        result = await self._git("push", "--quiet", "origin", f"{self.run_branch}:refs/heads/{self.run_branch}")
        if result.returncode != 0:
            return False, failure(result)
        return True, f"pushed {self.run_branch} to {self.url}"

    def push_command(self) -> str:
        return f"git -C {self.root} push origin {self.run_branch}"

    async def close(self) -> None:
        return None
