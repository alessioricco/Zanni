"""A verifier seat (D45): Zanni's built-in role `zanni:verifier`. It runs no model, and decides nothing.

For each `zanni.verify`, it reads every file of the stage over MCP into a fresh folder, runs exactly the command
the director sent within its timeout, and answers with the command's exit code: the verdict is the exit code.
"""

import tempfile
from pathlib import Path

from zanni.actor.contract import Stage, StageError
from zanni.commands import run_for_exit_code
from zanni.log import Log
from zanni.protocol.messages import Verdict, Verify

ROLE_FOLDER = Path(__file__).parent / "verifier_role"


async def pull_snapshot(stage: Stage, into: Path) -> tuple[str, list[str]]:
    """Every file the seat may read, written under `into`; (the stage's marker, files skipped as not text)."""
    marker = (await stage.changes())[1]
    skipped = []
    for path in await stage.list(""):
        try:
            text = await stage.read(path)
        except StageError as e:
            if e.code != "not-text":
                raise
            skipped.append(path)
            continue
        target = into / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return marker, skipped


async def run_verify(verify: Verify, stage: Stage, seat: str, log: Log, say) -> Verdict:
    say(f"  verify {verify.verify}: {verify.verifier}")
    log.event("verify", seat=seat, verify=verify.verify, verifier=verify.verifier, command=verify.command)
    with tempfile.TemporaryDirectory(prefix="zanni-verify-") as tmp:
        try:
            marker, skipped = await pull_snapshot(stage, Path(tmp))
        except StageError as e:
            code, output, marker = None, f"couldn't read the stage: {e.code}: {e}", verify.marker
        else:
            code, output = await run_for_exit_code(verify.command, tmp, int(verify.timeout))
            if skipped:
                output = f"(not text, so not in the snapshot: {', '.join(skipped)})\n{output}"
    verdict = Verdict(kind="zanni.verdict", verify=verify.verify, verifier=verify.verifier, passed=code == 0,
                      exit_code=None if code is None else str(code), output=output[-2000:], marker=marker)
    log.event("verdict", seat=seat, verify=verify.verify, verifier=verify.verifier, passed=verdict.passed,
              exit_code=verdict.exit_code, marker=marker)
    say(f"    {verify.verifier}: {'passed' if verdict.passed else 'failed'} (exit code {verdict.exit_code or 'none'})")
    return verdict
