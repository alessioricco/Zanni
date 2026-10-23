import subprocess
import sys

from zanni import __version__


def zanni(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "zanni", *args], capture_output=True, text=True)


def test_version():
    result = zanni("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == f"zanni {__version__}"


def test_no_file_prints_usage():
    result = zanni()
    assert result.returncode == 2
    assert "usage: zanni" in result.stderr + result.stdout
