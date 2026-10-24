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

A rehearsal runs one actor on cues from a file, against a fresh copy of a local stage. `zanni` starts a director for it on your machine, and the actor joins it over A2A, as it would join any director. The repository's example is the `slug-tester` role's `smoke` rehearsal, run through `examples/slug-tester.yaml`. That actor configuration lists `qwen3.8:27b` on Ollama, then `claude-haiku-5-5`, and takes `OLLAMA_BASE_URL` and `ANTHROPIC_API_KEY` from the environment. Edit its `models` to match yours, then:

```bash
set -a; . ./.env; set +a          # if your keys live in a .env: zanni reads the environment
uv run zanni examples/slug-tester.yaml
```

```
Rehearsal 'smoke' with slug-tester-1 (slug-tester 0.1.0); run 20261024T114513Z
  cue smoke-1: Specify
    done on ollama qwen3.8:27b: 4 tool calls, 3356 in / 294 out tokens, cost $0
  verify tests-pass: passed (2 passed in 0.01s)
Rehearsal passed. Stage and log: ~/.zanni/actors/slug-tester-1/rehearsals/smoke/20261024T114513Z
```

- **Order:** the actor runs on the first model in its configuration, and falls back to the next when one fails.
- **The stage copy:** the actor writes only to the copy, never to the role package.
- **The verdict:** the run passes when the rehearsal's `verify` checks pass. The exit code is 0 if it passed, and 1 if not.
- **Just checking:** `uv run zanni --check examples/slug-tester.yaml` validates the configuration and the rehearsal without running anything.

See [Writing a role](writing-a-role.md#6-rehearse-it) to rehearse your own role, and [Models and keys](models-and-keys.md) to set up models.

## Join a director on another machine

The director and the actor can run on different machines. Where an actor runs is up to whoever runs it (D32). Here one machine serves the `smoke` rehearsal, and an actor on another machine joins it.

1. **On the director's machine**, pick a join token, and serve the rehearsal on an address the other machine can reach:

   ```bash
   export ZANNI_JOIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
   uv run zanni examples/roles/slug-tester/rehearsals/smoke.yaml --serve --listen 0.0.0.0:8765
   ```

   ```
   Serving rehearsal 'smoke' for the role slug-tester at http://0.0.0.0:8765 (actors on other machines use this machine's address, port 8765); waiting for an actor
   ```

2. **On the actor's machine**, install Zanni (above), with the same version of the role: the director checks the role's hash, so a changed file is refused. Write an actor configuration whose `play` is the director's address, and give it the same join token:

   ```yaml
   # slug-tester-remote.yaml (chmod 600 if it stores the token)
   name: slug-tester-remote
   role: ./Zanni/examples/roles/slug-tester
   play: http://<director's address>:8765
   models:
     - { provider: ollama, model: qwen3.8:27b, base_url: "${OLLAMA_BASE_URL:-http://127.0.0.1:11434}", price: { input: 0, output: 0 } }
   credentials:
     ZANNI_JOIN_TOKEN: ${ZANNI_JOIN_TOKEN}
   ```

   `qwen3.8:27b` stands for any model with tool calling on this machine's own server, or a cloud model; see [Models and keys](models-and-keys.md).

3. **Run the actor:**

   ```bash
   export ZANNI_JOIN_TOKEN=<the same token>
   uv run --project Zanni zanni slug-tester-remote.yaml
   ```

   ```
   Joining the play 'rehearsal:smoke' (script …/rehearsals/smoke.yaml) at http://<director's address>:8765
   Cast as slug-tester-1 (part slug-tester); stage at http://<director's address>:8765/stage/mcp
     cue smoke-1: Specify
       done on ollama qwen3.8:27b: 4 tool calls, 3469 in / 404 out tokens, cost $0
   Released (done)
   The actor's log: ~/.zanni/actors/slug-tester-remote/plays
   ```

   The director then prints `Released slug-tester-1 (done)`, runs `verify`, and exits with `Rehearsal passed.`

- **Two logs:** the director keeps the run's log on its machine, under `~/.zanni/rehearsals/smoke/`; the actor keeps its own on its machine, under its state folder (D32).
- **Reaching the director:** only the director must be reachable; the actor connects out to it. A firewall on the director's machine may ask to allow incoming connections.
- **Plain HTTP:** `--serve` doesn't encrypt, so tokens cross the network in the clear. Use it on a network you trust, or behind a TLS proxy.
- **If it fails:** see [Troubleshooting](troubleshooting.md#joining-a-director).

The recorded runs of this layout are in [docs/runs/milestone-3.md](runs/milestone-3.md).

## What works today

| Works | Not yet |
|---|---|
| Validating actor configurations, plays, scripts, lockfiles, rehearsals and whole role folders | Starting a play's director from its play file, and casting a whole play (milestone 4) |
| Running one actor on a rehearsal, on local or cloud models, with fallback | Fetching remote roles (use a local folder for now) |
| An actor joining a director over A2A, by URL or through a play file's `director` | Renewing a seat's tokens: a seat ends when they expire, after 24 hours |
| Serving a rehearsal to an actor on another machine (`--serve`), with the stage over MCP | TLS: `--serve` speaks plain HTTP |
| Errors with their line and how to fix them | Fetching roles and scripts from git, or plays from URLs (only their shape is checked) |
| Rejecting secrets in shared files | Checking a play against a remote script (it needs fetching) |
| A summary of what each file would run | |

## Next steps

- [Concepts](concepts.md): what the pieces are and how they fit together.
- [Zanni files](files.md): every field of the three kinds of file.
- [Writing a role](writing-a-role.md): build your own role folder.
- [Writing a script](writing-a-script.md): write the work a play performs.
- [Contributing](contributing.md): if you want to work on Zanni itself.
