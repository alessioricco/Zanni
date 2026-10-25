"""Make this play's remote: a bare git repository, ./remote.git, whose `main` holds the software play's starter stage.

A repository can't ship inside this one, so the example makes its own, from ./stage. Any git remote works
as a stage's `url`, such as git@github.com:you/app.git; this one needs no account and no network.

    python3 make-remote.py          # once, in a copy of examples/
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REMOTE = HERE / "remote.git"
STAGE = HERE / "stage"


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "setup", "GIT_AUTHOR_EMAIL": "setup@zanni.invalid",
                        "GIT_COMMITTER_NAME": "setup", "GIT_COMMITTER_EMAIL": "setup@zanni.invalid",
                        "PATH": os.environ["PATH"], "HOME": str(cwd)})


def main() -> int:
    if REMOTE.exists():
        print(f"{REMOTE} already exists; delete it to start again from ./stage")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "stage"
        shutil.copytree(STAGE, work)
        git("init", "--quiet", "--initial-branch=main", cwd=work)
        git("add", ".", cwd=work)
        git("commit", "--quiet", "-m", "The software play's starter stage", cwd=work)
        git("clone", "--quiet", "--bare", str(work), str(REMOTE), cwd=Path(tmp))
    print(f"Made {REMOTE}, with the starter project on main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
