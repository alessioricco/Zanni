"""A play on a git stage (D46), end to end in another process: the run's own branch, one commit per write with the
seat as author, pushes at an approved gate and at the end, `push: approved | always` for an unfinished run, a push
that fails without stopping the play, and a repository that can't be cloned. Remotes are bare repositories in
tmp_path; nothing touches the network."""

import json
import signal
import subprocess

import pytest

import yaml

from tests.fake_openai import fake_openai
from tests.test_play_command import DIRECTOR_DONE, PY, env, play_folder, wait_until, zanni
from zanni.stage.git import run_git


def on_git(folder, tmp_path, push=None):
    """Turn the play's stage folder into a bare remote, and point the play at it."""
    stage, bare = folder / "stage", tmp_path / "remote.git"
    for args in (("init", "--quiet", "--initial-branch=main"), ("add", "."), ("commit", "--quiet", "-m", "seed")):
        assert run_git(*args, cwd=stage).returncode == 0
    assert run_git("clone", "--quiet", "--bare", str(stage), str(bare)).returncode == 0
    play = yaml.safe_load((folder / "play.yaml").read_text())
    play["stage"] = {"backend": "git", "url": "../remote.git"} | ({"push": push} if push else {})
    (folder / "play.yaml").write_text(yaml.safe_dump(play))
    return bare


def branches(bare):
    return run_git("branch", "--list", "--format=%(refname:short)", cwd=bare).stdout.split()


def run_to_gate(folder, tmp_path, before_approving=lambda: None):
    proc = subprocess.Popen([PY, "-m", "zanni", str(folder / "play.yaml")], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env(tmp_path), stdin=subprocess.DEVNULL)
    try:
        wait_until(lambda: "waiting at a gate" in zanni("gate", folder / "play.yaml", tmp_path=tmp_path).stdout, 90)
        before_approving()
        zanni("gate", folder / "play.yaml", "approve", tmp_path=tmp_path)
        out, err = proc.communicate(timeout=120)
    finally:
        proc.kill()
    return proc.returncode, out, err


def log_of(folder):
    return [json.loads(line) for line in next((folder / "log").glob("*.jsonl")).read_text().splitlines()]


def test_a_play_on_git_commits_each_write_by_its_seat_and_pushes_the_runs_branch(tmp_path):
    with fake_openai() as (url, _, scripts):
        scripts["director"] = list(DIRECTOR_DONE)
        folder = play_folder(tmp_path, url)
        bare = on_git(folder, tmp_path)
        code, out, err = run_to_gate(folder, tmp_path)
    assert code == 0, out + err
    run = log_of(folder)[0]["run"]
    branch = f"zanni/kata/{run}"
    assert sorted(branches(bare)) == ["main", branch]
    authors = run_git("log", "--format=%an|%s", f"main..{branch}", cwd=bare).stdout.splitlines()
    assert authors == ["coder-1|r1-c2: Build", "tester-1|r1-c1: Specify"]
    assert "app/slug.py" not in run_git("ls-tree", "-r", "--name-only", "main", cwd=bare).stdout  # main is untouched
    assert "app/slug.py" in run_git("ls-tree", "-r", "--name-only", branch, cwd=bare).stdout
    pushes = [e for e in log_of(folder) if e["event"] == "push"]
    assert [p["ok"] for p in pushes] == [True, True]
    assert "the approved gate plan" in pushes[0]["detail"] and "the end of the run" in pushes[1]["detail"]
    assert (folder / f"log/{run}-stage/app/slug.py").is_file()  # the clone stays in the run's folder


def unfinished(tmp_path, push):
    with fake_openai() as (url, _, scripts):
        scripts["director"] = [[("cue", {"target": "tester", "scene": "Specify", "instructions": "Write the tests.",
                                         "writes": ["tests/"]})], [("wait_for_reports", {})],
                               [("stop", {"reason": "stuck"})], "Stopped."]
        folder = play_folder(tmp_path, url)
        bare = on_git(folder, tmp_path, push)
        result = zanni(folder / "play.yaml", tmp_path=tmp_path)
    return folder, bare, result


def test_an_unfinished_run_isnt_pushed_under_push_approved_and_says_how_to_publish_it(tmp_path):
    folder, bare, result = unfinished(tmp_path, None)
    assert result.returncode == 1 and branches(bare) == ["main"]
    assert "not pushed (push: approved, and the play didn't finish). To publish it: git -C" in result.stdout
    assert not [e for e in log_of(folder) if e["event"] == "push"]


def test_an_unfinished_run_is_pushed_under_push_always(tmp_path):
    folder, bare, result = unfinished(tmp_path, "always")
    assert result.returncode == 1 and len(branches(bare)) == 2
    assert [e["ok"] for e in log_of(folder) if e["event"] == "push"] == [True]


def test_a_push_that_fails_is_logged_and_the_play_goes_on(tmp_path):
    with fake_openai() as (url, _, scripts):
        scripts["director"] = list(DIRECTOR_DONE)
        folder = play_folder(tmp_path, url)
        on_git(folder, tmp_path)

        def lose_the_remote():
            clone = next((folder / "log").glob("*-stage"))
            run_git("remote", "set-url", "origin", str(tmp_path / "gone.git"), cwd=clone)

        code, out, err = run_to_gate(folder, tmp_path, lose_the_remote)
    assert code == 0, out + err
    pushes = [e for e in log_of(folder) if e["event"] == "push"]
    assert [p["ok"] for p in pushes] == [False, False] and "couldn't push" in out and "the work stays in" in out
    assert "gone.git' does not appear to be a git repository" in pushes[0]["detail"]  # what failed, not git's advice


@pytest.mark.parametrize("push", ["approved", "always"])
def test_a_run_stopped_by_hand_is_published_as_push_says(tmp_path, push):
    with fake_openai() as (url, _, scripts):
        scripts["director"] = list(DIRECTOR_DONE)
        folder = play_folder(tmp_path, url)
        bare = on_git(folder, tmp_path, push)
        proc = subprocess.Popen([PY, "-m", "zanni", str(folder / "play.yaml")], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env(tmp_path), stdin=subprocess.DEVNULL)
        try:
            wait_until(lambda: "waiting at a gate" in zanni("gate", folder / "play.yaml", tmp_path=tmp_path).stdout, 90)
            proc.send_signal(signal.SIGINT)  # stopped by hand, at the gate: an unfinished run
            out, err = proc.communicate(timeout=60)
        finally:
            proc.kill()
    assert proc.returncode == 1, out + err
    pushes = [e["detail"] for e in log_of(folder) if e["event"] == "push"]
    if push == "always":
        assert len(pushes) == 1 and "the end of the run" in pushes[0] and len(branches(bare)) == 2
    else:
        assert pushes == [] and branches(bare) == ["main"] and "To publish it: git -C" in out


def test_a_repository_that_cant_be_cloned_starts_nothing(tmp_path):
    with fake_openai() as (url, calls, _):
        folder = play_folder(tmp_path, url)
        play = yaml.safe_load((folder / "play.yaml").read_text())
        play["stage"] = {"backend": "git", "url": "../no-such-repo.git"}
        (folder / "play.yaml").write_text(yaml.safe_dump(play))
        result = zanni(folder / "play.yaml", tmp_path=tmp_path)
        assert calls == []
    assert result.returncode == 2 and "couldn't clone" in result.stderr and "nothing was started" in result.stderr


def test_git_hides_its_own_folder_refuses_binary_reads_and_ignored_writes(tmp_path):
    import asyncio

    from tests.test_stage_backends import git_remote
    from zanni.stage import Stage, StageError
    from zanni.stage.git import GitBackend

    remote = git_remote(tmp_path, {".gitignore": "build/\n", "README.md": "hi\n"})
    work = tmp_path / "binary"
    assert run_git("clone", "--quiet", remote, str(work)).returncode == 0
    (work / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\xff\xfe")
    for args in (("add", "logo.png"), ("commit", "--quiet", "-m", "logo"), ("push", "--quiet", "origin", "main")):
        assert run_git(*args, cwd=work).returncode == 0
    stage = Stage(GitBackend.open(remote, "main", tmp_path / "clone", "zanni/p/r"))
    seat = stage.seat(["/"], ["/"], "coder-1")

    async def codes():
        out = {}
        for name, coro in (("git", seat.read(".git/config")), ("write-git", seat.write(".git/hooks/x", "x")),
                           ("binary", seat.read("logo.png")), ("ignored", seat.write("build/out.txt", "x"))):
            try:
                await coro
                out[name] = "ok"
            except StageError as e:
                out[name] = e.code
        out["listed"] = await seat.list()
        return out

    out = asyncio.run(codes())
    assert out["git"] == out["write-git"] == "invalid-path" and out["ignored"] == "invalid-path"
    assert out["binary"] == "not-text" and out["listed"] == [".gitignore", "README.md", "logo.png"]
    assert stage.marker() == 0
