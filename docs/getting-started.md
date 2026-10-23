# Getting started

## Install

Zanni needs Python 3.12 or newer. From a clone of the repository:

```bash
uv sync
uv run zanni --version
```

The package on PyPI is still a placeholder (0.0.1), so install from the repository for now.

## Check a file

The repository has examples of the three kinds of file in `examples/`:

```bash
uv run zanni examples/plays/habit-tracker/play.yaml
```

```
Play file: would start the director for the play 'habit-tracker'.
  director: wss://director.example.com
  stage: git@github.com:alessio/habit-tracker.git
  script: ./script.yaml
  cast:
    product-owner: github.com/zanni-roles/product-owner@1.0.0, 1 seat
    tester: github.com/someone/tester@1.4.0, 1 seat
    coder: github.com/zanni-roles/coder@1.0.0, 1-4 seats, started here (local)
  house rules: budget $20.00; human gates: plan, release
Valid. Nothing was started: running files comes in a later version (see ROADMAP.md).
```

`zanni` works out what kind of file it was given from the keys in the file, never from the name. It validates the file and prints what it would run.

If something is wrong, it lists every problem, each with its line and what to change, and exits with code 2:

```
play.yaml has 2 problems; nothing was started.
  play.yaml, line 9, cast.coder.hots: is not a known field; did you mean `host`?
  play.yaml, line 11, house_rules.budget: should be at least 0, not -1
```

| Exit code | Meaning |
|---|---|
| 0 | The file is valid |
| 2 | The file has problems, or no file was given |

## What doesn't work yet

- **Nothing starts:** no actors, directors or models.
- **Nothing is fetched:** role references and play URLs are checked for shape only.
- **Only the YAML files are checked:** `script.yaml`, `roles.lock` and the role folder's other files (`AGENTS.md`, `skills/`, `mcp.json`) aren't validated yet.

## Secrets

Zanni files never hold API keys. A key in a file that looks like a secret (`api_key`, `token`, `password` and similar) is rejected. Put secrets in the environment or a git-ignored `.env` file.
