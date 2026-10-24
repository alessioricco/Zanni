# Getting started

## What you need

- **Python 3.12 or newer.**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)**, which installs Zanni's dependencies and runs it.
- **git**, to clone the repository.

You don't need an API key or a local model server to check files. To run an actor, you need one model: a cloud key, or a local OpenAI-compatible server such as Ollama.

## Install

Zanni isn't installable from PyPI yet: the package there is a 0.0.1 placeholder that reserves the name. Install it from a clone:

```bash
git clone https://github.com/alessioricco/Zanni.git
cd Zanni
uv sync
uv run zanni --version
```

## Check a file

There is one command, `zanni <file>`. The repository has one example of each kind of file in `examples/`:

```bash
uv run zanni examples/plays/habit-tracker/play.yaml
```

```
Play file: would start the director for the play 'habit-tracker'.
  script: github.com/someone/habit-tracker@1.0.0
  director: https://director.example.com
  stage: git git@github.com:alessio/habit-tracker.git (branch main)
  cast:
    product-owner: github.com/zanni-roles/product-owner@1.0.0, 1 seat
    tester: github.com/someone/tester@1.4.0, 1 seat
    coder: github.com/zanni-roles/coder@1.0.0, 1-4 seats, started here (local)
  house rules: budget $20.00; human gates: plan, release
  script: remote, so the play wasn't checked against it (fetching scripts comes later)
Valid. Nothing was started: running files comes in a later version (see ROADMAP.md).
```

`zanni` works out what kind of file it was given from the keys in the file, never from the file's name. It validates the file and prints what it would run.

If something is wrong, it lists every problem, each with its line and what to change, and exits with code 2:

```
play.yaml has 2 problems; nothing was started.
  play.yaml, line 9, cast.coder.hots: is not a known field; did you mean `host`?
  play.yaml, line 11, house_rules.budget: should be at least 0, not -1
```

The other two examples:

```bash
uv run zanni examples/tester.yaml               # an actor configuration
uv run zanni examples/roles/tester              # a whole role folder
uv run zanni examples/scripts/software-team     # a script
uv run zanni examples/plays/newsroom/play.yaml  # a play, checked against its local script
```

## Run an actor: a rehearsal

A rehearsal runs one actor on cues from a file, against a fresh copy of a local stage, with no director. The repository's example is the `slug-tester` role's `smoke` rehearsal, run through `examples/slug-tester.yaml`. That actor configuration lists `qwen3.8:27b` on Ollama, then `claude-haiku-5-5`, and takes `OLLAMA_BASE_URL` and `ANTHROPIC_API_KEY` from the environment. Edit its `models` to match yours, then:

```bash
set -a; . ./.env; set +a          # if your keys live in a .env: zanni reads the environment
uv run zanni examples/slug-tester.yaml
```

```
Rehearsal 'smoke' with slug-tester-1 (slug-tester 0.1.0); run 20261024T001644Z
  cue 1/1: Specify
    done on ollama qwen3.8:27b: 4 tool calls, 3361 in / 344 out tokens, cost $0
  verify tests-pass: passed (2 passed in 0.01s)
Rehearsal passed. Stage and log: ~/.zanni/actors/slug-tester-1/rehearsals/smoke/20261024T001644Z
```

- **Order:** the actor runs on the first model in its configuration, and falls back to the next when one fails.
- **The stage copy:** the actor writes only to the copy, never to the role package.
- **The verdict:** the run passes when the rehearsal's `verify` checks pass. The exit code is 0 if it passed, and 1 if not.
- **Just checking:** `uv run zanni --check examples/slug-tester.yaml` validates the configuration and the rehearsal without running anything.

See [Writing a role](writing-a-role.md#6-rehearse-it) to rehearse your own role, and [Models and keys](models-and-keys.md) to set up models.

## What works today

| Works | Not yet |
|---|---|
| Validating actor configurations, plays, scripts, lockfiles, rehearsals and whole role folders | Joining a director, or starting one (milestones 3 and 4) |
| Running one actor on a rehearsal, on local or cloud models, with fallback | Fetching remote roles (use a local folder for now) |
| Errors with their line and how to fix them | Fetching roles and scripts from git, or plays from URLs (only their shape is checked) |
| Rejecting secrets in shared files | Checking a play against a remote script (it needs fetching) |
| A summary of what each file would run | |

## Next steps

- [Concepts](concepts.md): what the pieces are and how they fit together.
- [Zanni files](files.md): every field of the three kinds of file.
- [Writing a role](writing-a-role.md): build your own role folder.
- [Writing a script](writing-a-script.md): write the work a play performs.
- [Contributing](contributing.md): if you want to work on Zanni itself.
