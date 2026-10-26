"""`zanni:workspace` (D52): an MCP server, over stdio, on the official `mcp` SDK, that an actor runs for itself.

It serves one folder, the seat's workspace: a local copy of the stage the actor fills at the start of each cue and
sends back at its end (src/zanni/actor/workspace.py). Its tools read, write and list files inside the folder, and
`run` a command there, but only one named in the actor configuration's `workspace.commands`: what runs on a machine
is its owner's decision. Nothing here touches the stage, and nothing here decides "done" (D45).

    python -m zanni.engine.workspace_server --folder <path> [--command <name>]... [--timeout <seconds>]
"""

import argparse
import asyncio
import contextlib
import os
import signal
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

OUTPUT_TAIL = 8000  # characters of a command's output returned to the model


def inside(folder: Path, path: str) -> Path:
    """`path` within the folder; anything that would leave it, through `..`, an absolute path or a link, is refused."""
    if not path or path.startswith("/") or "\\" in path:
        raise ToolError(f"invalid-path: {path!r} isn't a path inside the workspace; write it relative to it, with /")
    target = (folder / path).resolve()
    if not target.is_relative_to(folder):
        raise ToolError(f"invalid-path: {path} leads outside the workspace")
    return target


def workspace_server(folder: Path, commands: list[str], timeout: int, groups: set[int] | None = None) -> MCPServer:
    """`groups` collects the process group of every command `run` starts, for `main` to stop when the server ends."""
    folder = folder.resolve()
    groups = set() if groups is None else groups
    server = MCPServer("zanni-workspace", log_level="WARNING", instructions=(
        "Your workspace: a local copy of the stage, for this cue. Edit files here, and run the project's commands "
        "here. What you change is sent to the stage when the cue ends, within the cue's paths."))

    @server.tool()
    def read_file(path: str) -> str:
        """Read a text file from the workspace. Paths are relative to it, e.g. app/convert.py."""
        target = inside(folder, path)
        if not target.is_file():
            raise ToolError(f"not-found: {path} isn't in the workspace")
        try:
            return target.read_text()
        except UnicodeDecodeError:
            raise ToolError(f"not-text: {path} isn't a text file") from None

    @server.tool()
    def write_file(path: str, content: str) -> str:
        """Write a whole text file in the workspace, replacing it if it exists; folders are made as needed."""
        target = inside(folder, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {path}"

    @server.tool()
    def list_files(path: str = "") -> list[str]:
        """List the files under a folder of the workspace, at any depth; empty for the whole workspace."""
        root = inside(folder, path) if path else folder
        if not root.is_dir():
            raise ToolError(f"not-found: {path} isn't a folder in the workspace")
        return sorted(p.relative_to(folder).as_posix() for p in root.rglob("*")
                      if p.is_file() and ".git" not in p.relative_to(folder).parts)

    @server.tool()
    async def run(command: list[str], timeout_seconds: int = 120) -> dict:
        """Run a command in the workspace, such as the project's tests, and get its exit code and the end of its
        output. Only the commands this actor's owner allows can run."""
        if not command:
            raise ToolError("invalid-command: give the command as a list, e.g. [\"npm\", \"test\"]")
        name = command[0]
        if "/" in name or "\\" in name or name not in commands:
            allowed = ", ".join(commands) or "none: this actor's configuration lists no workspace.commands"
            raise ToolError(f"not-permitted: {name} isn't a command this actor may run; it may run: {allowed}")
        limit = max(1, min(timeout_seconds, timeout))
        try:
            proc = await asyncio.create_subprocess_exec(*command, cwd=folder, stdin=asyncio.subprocess.DEVNULL,
                                                        stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            return {"exit_code": None, "output": f"couldn't start {name}: {e}"}
        groups.add(proc.pid)  # what it leaves running, such as an app for the next call, lives until the cue ends
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), limit)
        except TimeoutError:
            stop_group(proc.pid)
            out, _ = await proc.communicate()
            return {"exit_code": None, "output": f"stopped after {limit} s\n"
                                                 + out.decode(errors="replace")[-OUTPUT_TAIL:]}
        finally:  # a call cancelled, or the server stopping, must not leave the command running (found by milestone 6)
            if proc.returncode is None:
                stop_group(proc.pid)
        return {"exit_code": proc.returncode, "output": out.decode(errors="replace")[-OUTPUT_TAIL:]}

    return server


def stop_group(pid: int) -> None:
    """Kill a command and everything it started: it runs in a session of its own."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGKILL)


def main() -> None:
    parser = argparse.ArgumentParser(prog="zanni-workspace")
    parser.add_argument("--folder", required=True, type=Path)
    parser.add_argument("--command", action="append", default=[], dest="commands")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=True)
    groups: set[int] = set()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # the client's stop: still run the finally below
    try:
        workspace_server(args.folder, args.commands, args.timeout, groups).run("stdio")
    finally:  # the cue is over: nothing a command started outlives it (found by milestone 6's runs)
        for group in groups:
            stop_group(group)


if __name__ == "__main__":
    main()
