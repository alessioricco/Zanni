---
name: slug-kata
version: 0.1.0
mission: Turn a small backlog into tested Python, a round at a time, each change checked by the tests.
parts:
  tester:
    description: Writes a failing pytest test for every acceptance criterion.
    suggested: ../../roles/slug-tester
    writes: [tests/]
  coder:
    description: Makes the tests pass, one backlog item per seat.
    suggested: ../../roles/slug-coder
    seats: 1-2
    writes: [app/]
stage:
  expects: [vision.md, backlog/round-1.md]
gates: [plan]
verifiers:
  tests-fail:
    description: the tests run, and at least one fails (new tests fail before the code exists)
    command: [uv, run, --no-project, --with, pytest, python, -c, "import subprocess, sys; sys.exit(0 if subprocess.call([sys.executable, '-m', 'pytest', '-q', 'tests']) == 1 else 1)"]
  tests-pass:
    description: every test passes
    command: [uv, run, --no-project, --with, pytest, python, -m, pytest, -q, tests]
stop:
  max_rounds: 2
  done_when: [tests-pass]
---

# Slug kata

Each round takes the next backlog file, `backlog/round-<n>.md`, starting with round 1. When a round's tests all
pass and there is a next backlog file, start the next round; when there is none, the play is done.

## Act 1: a round (repeat until a stop rule)

### Scene 1: Specify
The **tester** reads `backlog/round-<n>.md` and `spec/`, and writes one failing test per acceptance criterion
into `tests/`, one test file per backlog item (for example `tests/test_slug.py` and `tests/test_words.py`).
Tell it which module each item's code lives in, as the spec says.
*Verifier:* `tests-fail`.

**Gate: plan.** A person approves the tests before any code is written.

### Scene 2: Build
Cast one **coder** per backlog item, up to two, and give each one item: its module in `app/`, and its tests.
Coders work at the same time, each only in its own module.
*Verifier:* `tests-pass`. If it fails, give the coder whose tests fail one more cue with the failure.

### Scene 3: Close the round
When `tests-pass` passes, end the round, or stop the play as done if this was the last backlog file.
