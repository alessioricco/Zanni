"""Conformance: any implementation of the `zanni` command must accept every file in valid/ and reject
every file in invalid/, pointing at the line and field its .expected sidecar names.

Run against another implementation with ZANNI_CMD, e.g. ZANNI_CMD="my-zanni" uv run pytest tests/conformance
"""

import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
COMMAND = shlex.split(os.environ.get("ZANNI_CMD", "uv run zanni"))


def run(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([*COMMAND, "--check", str(path)], capture_output=True, text=True, timeout=60)


def expected(path: Path) -> dict[str, str]:
    sidecar = path.with_suffix(".expected") if path.is_file() else path.parent / f"{path.name}.expected"
    lines = sidecar.read_text().splitlines()
    return {k.strip(): v.strip() for k, _, v in (line.partition(":") for line in lines)}


def cases(folder: str) -> list[Path]:
    """Each case is a .yaml or .md file, or a folder (such as a role package)."""
    root = HERE / folder
    return sorted(p for p in root.iterdir() if p.suffix in (".yaml", ".md") or p.is_dir())


@pytest.mark.parametrize("path", cases("valid"), ids=lambda p: p.name)
def test_valid(path):
    result = run(path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("path", cases("invalid"), ids=lambda p: p.name)
def test_invalid(path):
    result = run(path)
    assert result.returncode == 2, f"expected exit 2, got {result.returncode}\n{result.stdout}"
    want = expected(path)
    problems = result.stderr.splitlines()
    match = [p for p in problems
             if (not want["line"] or re.search(rf"\bline {want['line']}\b", p)) and (not want["path"] or f" {want['path']}:" in p)]
    assert match, f"no problem at line {want['line'] or '-'}, field {want['path'] or '-'}:\n{result.stderr}"
