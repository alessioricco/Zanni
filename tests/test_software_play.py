"""D58: one full round of the software script, end to end from a copy of examples/, with the director and all six
seats scripted on a fake OpenAI-compatible server: the backlog and its review loop (D59), the plan gate holding back
the spec until approved (D62), the spec and its review loop, tests, tasks, the coder's workspace (D52), the
verifiers and their check files (D55), exploring into findings, and the release gate; every write a commit by its
seat on the run's branch (D46)."""

import json
import os
import shutil
import subprocess
import time

import yaml

from tests.fake_openai import fake_openai
from tests.test_check_files import free_port
from tests.test_slug_kata import EXAMPLES, PY, entry
from zanni.stage.git import run_git

TOKENS = {"ZANNI_JOIN_TOKEN": "join-token-fake", "ZANNI_OWNER_TOKEN": "owner-token-fake"}
SEATS = ["product-owner-1", "architect-1", "ui-designer-1", "tester-1", "developer-lead-1", "coder-1"]

BACKLOG = "# Round 1\n\n## Convert lengths\n- R1-1: 1 km is 1000 m\n- R1-2: 12 in is 30.48 cm\n"
REVISED = BACKLOG + "\n## Show it\n- R1-3: the page at / answers\n"
DESIGN = "# Architecture\n\n- `app/convert.py`: convert(value, from_unit, to_unit)\n- `app/__main__.py`: the page\n"
TESTS = """from app.convert import convert


def test_r1_1_km_to_m():
    assert convert(1, "km", "m") == 1000


def test_r1_2_in_to_cm():
    assert round(convert(12, "in", "cm"), 2) == 30.48


def test_r1_3_page_is_served():
    import app.__main__ as page
    assert "<form" in page.PAGE
"""
FINDING_TEST = "def test_finding_negative_values():\n    assert False, 'negative lengths are accepted'\n"
CONVERT = ("FACTORS = {'m': 1.0, 'km': 1000.0, 'cm': 0.01, 'in': 0.0254}\n\n\n"
           "def convert(value, from_unit, to_unit):\n    return value * FACTORS[from_unit] / FACTORS[to_unit]\n")
MAIN = '''import http.server
import os

PAGE = "<form><input name=value><select name=from></select><select name=to></select></form>"


class Page(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "8000"))), Page).serve_forever()
'''


def write(path, content, tool="stage_write"):
    return [(f"{'workspace_write_file' if tool == 'workspace' else 'stage_write'}", {"path": path, "content": content})]


def cue(target, scene, writes, instructions="Do your part of this scene."):
    return ("cue", {"target": target, "scene": scene, "instructions": instructions, "writes": writes})


WAIT = [("wait_for_reports", {})]


def scripts(scripted):
    scripted["product-owner"] = [write("backlog/round-1.md", BACKLOG), "Done.",
                                 write("backlog/round-1.md", REVISED)
                                 + write("reviews/round-1/backlog-answers.md", "1. Added R1-3.\n"), "Done.",
                                 write("reviews/round-1/review.md", "Lengths work. Next: weights.\n"), "Done."]
    scripted["architect"] = [write("reviews/round-1/backlog-architect.md", "1. R1-2 needs a tolerance.\n"), "Done.",
                             write("spec/architecture/overview.md", DESIGN), "Done.",
                             write("spec/architecture/overview.md", DESIGN + "\nRounded to 2 places.\n")
                             + write("reviews/round-1/spec-answers.md", "1. Rounding added.\n"), "Done."]
    scripted["ui-designer"] = [write("spec/ui/converter.md", "# / \n\nServes R1-3: a form.\n"), "Done."]
    scripted["tester"] = [write("reviews/round-1/backlog-tester.md", "1. R1-3 is vague.\n"), "Done.",
                          write("reviews/round-1/spec-tester.md", "1. Name the page's form.\n"), "Done.",
                          write("tests/test_convert.py", TESTS, "workspace"), "Done.",
                          write("findings/negative-values.md", "Negative lengths convert silently.\n", "workspace")
                          + write("tests/findings/test_negative.py", FINDING_TEST, "workspace"), "Done."]
    scripted["developer-lead"] = [write("reviews/round-1/spec-developer-lead.md", "1. One workstream is enough.\n"),
                                  "Done.", write("tasks/round-1.md", "## convert\npaths: [app/]\n"), "Done."]
    scripted["coder"] = [write("app/__init__.py", "", "workspace") + write("app/convert.py", CONVERT, "workspace")
                         + write("app/__main__.py", MAIN, "workspace"), "Done."]
    scripted["director"] = [
        [cue("product-owner", "Plan", ["backlog/round-1.md"])], WAIT,
        [cue("architect", "Specify", ["spec/architecture/"])],  # refused: the plan gate holds back spec/ (D62)
        [cue("architect", "Backlog review", ["reviews/round-1/backlog-architect.md"]),
         cue("tester", "Backlog review", ["reviews/round-1/backlog-tester.md"])], WAIT,
        [cue("product-owner", "Backlog review", ["backlog/round-1.md", "reviews/round-1/backlog-answers.md"])], WAIT,
        [("ask_gate", {"name": "plan", "summary": "Three criteria, reviewed and revised."})],
        [cue("architect", "Specify", ["spec/architecture/"]), cue("ui-designer", "Specify", ["spec/ui/"])], WAIT,
        [cue("tester", "Spec review", ["reviews/round-1/spec-tester.md"]),
         cue("developer-lead", "Spec review", ["reviews/round-1/spec-developer-lead.md"])], WAIT,
        [cue("architect", "Spec review", ["spec/architecture/", "reviews/round-1/spec-answers.md"])], WAIT,
        [cue("tester", "Tests", ["tests/"])], WAIT,
        [("run_verifier", {"name": "tests-cover-criteria"})], [("run_verifier", {"name": "new-tests-fail"})],
        [cue("developer-lead", "Build", ["tasks/round-1.md"])], WAIT,
        [cue("coder", "Build", ["app/"])], WAIT,
        [("run_verifier", {"name": "tests-pass"})], [("run_verifier", {"name": "app-starts"})],
        [cue("tester", "Explore", ["findings/", "tests/findings/"])], WAIT,
        [cue("product-owner", "Review", ["reviews/round-1/review.md"])], WAIT,
        [("run_verifier", {"name": "tests-pass"})], [("run_verifier", {"name": "app-starts"})],
        [("ask_gate", {"name": "release", "summary": "Lengths convert; one finding for round 2."})],
        [("stop", {"reason": "done", "done": True})],
        "The round is done.",
    ]


def configure(play, url, tmp_path):
    doc = yaml.safe_load((play / "play.yaml").read_text())
    script = "${ZANNI_SCRIPT}/checks"
    pytest = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests", "--ignore=tests/findings"]
    doc["verifiers"] = {  # this Python's tools in place of uv, since the suite has no network (D35)
        "tests-cover-criteria": {"command": [PY, f"{script}/criteria.py", "backlog", "tests"]},
        "new-tests-fail": {"command": [PY, f"{script}/expect_failure.py", "--code", "1", "--code", "2", "--", *pytest]},
        "tests-pass": {"command": pytest},
        "app-starts": {"command": [PY, f"{script}/app_starts.py", "--port", str(free_port()), "--", PY, "-m", "app"]}}
    (play / "play.yaml").write_text(yaml.safe_dump(doc))
    for name in ["director", *SEATS]:
        doc = yaml.safe_load((play / f"{name}.yaml").read_text())
        doc["models"] = [entry(name.removesuffix("-1"), url)]
        doc["credentials"] = {k: v for k, v in doc.get("credentials", {}).items() if k.startswith("ZANNI_")}
        doc["state_dir"] = str(tmp_path / "state" / name)
        (play / f"{name}.yaml").write_text(yaml.safe_dump(doc))


def run_approving_every_gate(play, env):
    director = subprocess.Popen([PY, "-m", "zanni", str(play / "play.yaml")], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env, stdin=subprocess.DEVNULL)
    approved = 0
    try:
        until = time.monotonic() + 240
        while director.poll() is None and time.monotonic() < until:
            shown = subprocess.run([PY, "-m", "zanni", "gate", str(play / "play.yaml")], capture_output=True,
                                   text=True, env=env)
            if "waiting at a gate" in shown.stdout:
                subprocess.run([PY, "-m", "zanni", "gate", str(play / "play.yaml"), "approve"], capture_output=True,
                               text=True, env=env)
                approved += 1
            time.sleep(0.3)
        out, err = director.communicate(timeout=60)
    finally:
        director.kill()
    return director.returncode, out, err, approved


def test_one_round_of_the_software_script_runs_end_to_end(tmp_path):
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), **TOKENS}
    shutil.copytree(EXAMPLES, tmp_path / "examples")
    play = tmp_path / "examples/plays/software-mini-python"
    made = subprocess.run([PY, "make-remote.py"], cwd=play, capture_output=True, text=True)
    assert made.returncode == 0, made.stderr
    with fake_openai() as (url, _, scripted):
        scripts(scripted)
        configure(play, url, tmp_path)
        code, out, err, approved = run_approving_every_gate(play, env)
    assert code == 0, out + err
    assert approved == 2 and "The play is done." in out
    log = [json.loads(line) for line in next((play / "log").glob("2*.jsonl")).read_text().splitlines()]
    refused = [e["reason"] for e in log if e["event"] == "tool-refused"]
    assert any("plan must be approved in this round before any cue writes spec/" in r for r in refused)
    verdicts = [(e["verifier"], e["passed"]) for e in log if e["event"] == "verdict"]
    assert verdicts == [("tests-cover-criteria", True), ("new-tests-fail", True), ("tests-pass", True),
                        ("app-starts", True), ("tests-pass", True), ("app-starts", True)]
    assert not [e for e in log if e["event"] == "report" and e.get("refused")]
    run = log[0]["run"]
    branch = f"zanni/software-mini-python/{run}"
    authors = set(run_git("log", "--format=%an", f"main..{branch}", cwd=play / "remote.git").stdout.split())
    parts = {seat.rsplit("-", 1)[0] for seat in SEATS}
    # every part's work, as commits by its own seat, on the run's branch; a seat lost on a busy machine is recast,
    # such as tester-2 for tester-1 (D36), and is still that part
    assert {author.rsplit("-", 1)[0] for author in authors} == parts
    files = run_git("ls-tree", "-r", "--name-only", branch, cwd=play / "remote.git").stdout.split()
    for path in ("backlog/round-1.md", "reviews/round-1/backlog-answers.md", "reviews/round-1/spec-answers.md",
                 "spec/ui/converter.md", "tests/test_convert.py", "tasks/round-1.md", "app/convert.py",
                 "findings/negative-values.md", "tests/findings/test_negative.py", "reviews/round-1/review.md"):
        assert path in files, path
    assert not any("__pycache__" in f for f in files)  # the workspace sends no build output


def test_the_two_plays_differ_only_in_their_project():
    """D56: the same script, roles and seats on two stacks; only the verifier commands, the starter files and what the
    workspaces may run differ."""
    python, node = EXAMPLES / "plays/software-mini-python", EXAMPLES / "plays/software-mini-node"

    def without(doc: dict, *keys) -> dict:
        return {k: v for k, v in doc.items() if k not in keys}

    plays = [yaml.safe_load((p / "play.yaml").read_text()) for p in (python, node)]
    assert without(plays[0], "name", "verifiers") == without(plays[1], "name", "verifiers")
    assert set(plays[0]["verifiers"]) == set(plays[1]["verifiers"]) == {"new-tests-fail", "tests-pass", "app-starts"}
    for name in ["director", *SEATS]:
        docs = [yaml.safe_load((p / f"{name}.yaml").read_text()) for p in (python, node)]
        assert without(docs[0], "workspace") == without(docs[1], "workspace"), name
    assert sorted(p.name for p in (python / "stage").iterdir()) == [".gitignore", "pyproject.toml", "vision.md"]
    assert sorted(p.name for p in (node / "stage").iterdir()) == [".gitignore", "package.json", "vision.md"]
