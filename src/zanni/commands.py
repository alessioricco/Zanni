"""Running a verifier's command (D35, D45): in a snapshot of the stage, with the permissions of whoever runs it
(the director, or a verifier seat), within a timeout.

A verifier passes when its command exits 0. A timeout kills the command's whole process group, so a test runner's
child processes don't outlive it on an unattended machine.
"""

import asyncio
import contextlib
import os
import signal
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path

OUTPUT = 2000  # characters of a verifier's output kept for the director's model and the log
SCRIPT_VAR = "${ZANNI_SCRIPT}"  # where a verifier's command finds its script's check files (D55)


@contextlib.contextmanager
def with_script_files(command: list[str], files: Mapping[str, str]) -> Iterator[list[str]]:
    """Put a verifier's check files in a fresh folder, never on the stage, and give the command with every
    ${ZANNI_SCRIPT} replaced by that folder (D55). The folder goes when the command is done."""
    with tempfile.TemporaryDirectory(prefix="zanni-script-") as tmp:
        root = Path(tmp).resolve()
        for path, text in files.items():
            target = (root / path).resolve()
            if not target.is_relative_to(root) or target == root:
                raise ValueError(f"{path!r} isn't a path inside the script's package")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        yield [arg.replace(SCRIPT_VAR, str(root)) for arg in command]


async def run_command(command: list[str], cwd, timeout: int) -> tuple[bool, str]:
    """(passed, the end of its output)."""
    code, detail = await run_for_exit_code(command, cwd, timeout)
    return code == 0, detail


def project_env() -> dict[str, str]:
    """The environment a project's own command runs in: this one, without Zanni's own virtual environment, which
    belongs to Zanni, not to the project (found by milestone 6's runs: `uv run` warned on every verdict)."""
    return {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}


async def run_for_exit_code(command: list[str], cwd, timeout: int) -> tuple[int | None, str]:
    """(the exit code, or None when it timed out, couldn't start or was killed by a signal; the end of its output)."""
    try:
        proc = await asyncio.create_subprocess_exec(*command, cwd=cwd, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.STDOUT, start_new_session=True,
                                                    env=project_env())
    except OSError as e:
        return None, f"couldn't start {command[0]}: {e}"
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        _kill_group(proc.pid)
        await proc.wait()
        return None, f"timed out after {timeout} s, and was stopped"
    finally:  # cancelled, such as when the play stops: the command must not outlive it
        if proc.returncode is None:
            _kill_group(proc.pid)
    text = out.decode(errors="replace").strip()
    code = proc.returncode if proc.returncode >= 0 else None
    return code, (text[-OUTPUT:] or f"exit code {proc.returncode}")


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
