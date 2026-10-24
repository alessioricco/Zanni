"""Live: run a real rehearsal on a real model. Skipped unless ZANNI_LIVE_CONFIG names an actor configuration.

    ZANNI_LIVE_CONFIG=~/zanni/slug-tester.yaml uv run pytest tests/live

The actor configuration's `play` must point at a rehearsal; its models and credentials are used as they are.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

CONFIG = os.environ.get("ZANNI_LIVE_CONFIG")


@pytest.mark.skipif(not CONFIG, reason="set ZANNI_LIVE_CONFIG to an actor configuration whose play is a rehearsal")
def test_live_rehearsal_passes():
    path = Path(CONFIG).expanduser()
    result = subprocess.run([sys.executable, "-m", "zanni", str(path)], capture_output=True, text=True, timeout=900)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Rehearsal passed." in result.stdout
