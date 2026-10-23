# Getting started

## What you need

- **Python 3.12 or newer.**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)**, which installs Zanni's dependencies and runs it.
- **git**, to clone the repository.

You don't need an API key or a local model server: nothing in Zanni calls a model yet.

## Install

Zanni isn't installable from PyPI yet: the package there is a 0.0.1 placeholder that reserves the name. Install it from a clone:

```bash
git clone https://github.com/alessioricco/zanni.git
cd zanni
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
  director: wss://director.example.com
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

## What works today

| Works | Not yet |
|---|---|
| Validating actor configurations, plays, scripts, lockfiles and whole role folders | Starting an actor or a director |
| Errors with their line and how to fix them | Fetching roles and scripts from git, or plays from URLs (only their shape is checked) |
| Rejecting secrets in shared files | Checking a play against a remote script (it needs fetching) |
| A summary of what each file would run | Calling any model |

## Next steps

- [Concepts](concepts.md): what the pieces are and how they fit together.
- [Zanni files](files.md): every field of the three kinds of file.
- [Writing a role](writing-a-role.md): build your own role folder.
- [Writing a script](writing-a-script.md): write the work a play performs.
- [Contributing](contributing.md): if you want to work on Zanni itself.
