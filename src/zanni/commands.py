"""Running a verifier's command (D35, D45): in a snapshot of the stage, with the permissions of whoever runs it
(the director, or a verifier seat), within a timeout.

A verifier passes when its command exits 0. A timeout kills the command's whole process group, so a test runner's
child processes don't outlive it on an unattended machine.
"""

import asyncio
import os
import signal

OUTPUT = 2000  # characters of a verifier's output kept for the director's model and the log


async def run_command(command: list[str], cwd, timeout: int) -> tuple[bool, str]:
    """(passed, the end of its output)."""
    code, detail = await run_for_exit_code(command, cwd, timeout)
    return code == 0, detail


async def run_for_exit_code(command: list[str], cwd, timeout: int) -> tuple[int | None, str]:
    """(the exit code, or None when it timed out, couldn't start or was killed by a signal; the end of its output)."""
    try:
        proc = await asyncio.create_subprocess_exec(*command, cwd=cwd, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.STDOUT, start_new_session=True)
    except OSError as e:
        return None, f"couldn't start {command[0]}: {e}"
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        _kill_group(proc.pid)
        await proc.wait()
        return None, f"timed out after {timeout} s, and was stopped"
    text = out.decode(errors="replace").strip()
    code = proc.returncode if proc.returncode >= 0 else None
    return code, (text[-OUTPUT:] or f"exit code {proc.returncode}")


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
