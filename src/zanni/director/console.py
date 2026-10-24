"""When the director runs in an interactive terminal, a person there may decide too (D38): a convenience, never a
dependency, since a director often runs in the background. The same decisions as `zanni gate`, by "console"."""

import asyncio
import sys
import threading
from collections.abc import Callable

from zanni.director.gates import Gates

HELP = "type approve, reject <note> or resume here, or use zanni gate from anywhere"


def stdin_lines(loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
    """Lines typed in the terminal, read by a daemon thread (it never holds the director's shutdown up)."""
    queue: asyncio.Queue = asyncio.Queue()

    def read():
        for line in sys.stdin:
            loop.call_soon_threadsafe(queue.put_nowait, line)
        loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=read, daemon=True, name="zanni-console").start()
    return queue


async def console(gates: Gates, lines: asyncio.Queue, say: Callable[[str], None] = print) -> None:
    """Run until cancelled: each line typed is a decision, taken like the owner's."""
    async def hint():
        while True:
            await gates.changed.wait()
            gates.changed.clear()
            if gates.state_name in ("gate", "paused"):
                say(f"  ({HELP})")

    hinting = asyncio.create_task(hint())
    try:
        while (line := await lines.get()) is not None:
            action, _, note = line.strip().partition(" ")
            if not action:
                continue
            problem = gates.decide(action.lower(), note.strip(), by="console")
            say(f"  {problem}" if problem else f"  {action.lower()}: taken")
    finally:
        hinting.cancel()
