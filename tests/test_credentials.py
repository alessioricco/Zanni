"""D15: an actor configuration may hold its credentials, but zanni protects them. Only fake keys appear here."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FAKE = "sk-fake-0000-not-a-real-key"
CONFIG = f"""name: tester-1
role: roles/tester
play: ./play.yaml
models:
  - {{ provider: anthropic, model: claude-sonnet-5-5, credential: ANTHROPIC_API_KEY }}
credentials:
  ANTHROPIC_API_KEY: {FAKE}
  GITHUB_TOKEN: ${{GITHUB_TOKEN}}
"""


def zanni(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "zanni", str(path)], capture_output=True, text=True)


def write(tmp_path: Path, text: str = CONFIG, mode: int = 0o600) -> Path:
    path = tmp_path / "tester.yaml"
    path.write_text(text)
    path.chmod(mode)
    return path


def test_private_file_with_stored_credentials_is_valid_and_values_stay_hidden(tmp_path):
    result = zanni(write(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "ANTHROPIC_API_KEY (stored, hidden), GITHUB_TOKEN (from the environment)" in result.stdout
    assert FAKE not in result.stdout + result.stderr


def test_file_other_users_can_read_is_refused(tmp_path):
    path = write(tmp_path, mode=0o644)
    result = zanni(path)
    assert result.returncode == 2
    assert f"line 6, credentials: holds credentials, but other users can read this file (mode 644); run: chmod 600 {path}" \
        in result.stderr
    assert FAKE not in result.stderr


def test_only_references_need_no_private_file(tmp_path):
    text = CONFIG.replace(FAKE, "${ANTHROPIC_API_KEY}")
    assert zanni(write(tmp_path, text, mode=0o644)).returncode == 0


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_file_git_tracks_is_refused(tmp_path):
    path = write(tmp_path)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "add", path.name], cwd=tmp_path, check=True, env=env)
    result = zanni(path)
    assert result.returncode == 2
    assert "credentials: holds credentials, but git tracks this file" in result.stderr
    assert FAKE not in result.stderr


def test_a_bad_credential_value_is_reported_without_showing_it(tmp_path):
    result = zanni(write(tmp_path, CONFIG.replace(FAKE, "[1, 2]")))
    assert result.returncode == 2
    assert "credentials.ANTHROPIC_API_KEY: should be text, not a value (hidden)" in result.stderr


def test_secret_outside_credentials_is_refused(tmp_path):
    text = CONFIG.replace("credential: ANTHROPIC_API_KEY }", f"api_key: {FAKE} }}")
    result = zanni(write(tmp_path, text))
    assert result.returncode == 2
    assert "models[0].api_key: looks like a secret, and only an actor configuration's `credentials` may hold one; " \
           "move it to this file's `credentials` section" in result.stderr


def test_model_naming_a_missing_credential(tmp_path):
    text = CONFIG.replace("credential: ANTHROPIC_API_KEY", "credential: OPENAI_API_KEY")
    result = zanni(write(tmp_path, text))
    assert result.returncode == 2
    assert "models[0] uses the credential OPENAI_API_KEY, which isn't in `credentials`" in result.stderr
