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

There is one command, `zanni <file>`. With `--check`, it only validates the file and prints what it would run; without it, an actor configuration or a play runs. The repository has an example of each kind of file in `examples/`:

```bash
uv run zanni --check examples/plays/habit-tracker/play.yaml
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
  house rules: budget $20.00; human gates: plan, release; at most 30 director turns per round
  script: remote, so it is checked when the director fetches it (D37)
Valid.
```

`zanni` works out what kind of file it was given from the keys in the file, never from the file's name. It validates the file and prints what it would run.

If something is wrong, it lists every problem, each with its line and what to change, and exits with code 2:

```
play.yaml has 2 problems; nothing was started.
  play.yaml, line 9, cast.coder.hots: is not a known field; did you mean `host`?
  play.yaml, line 11, house_rules.budget: should be at least 0, not -1
```

The other examples:

```bash
uv run zanni --check examples/tester.yaml               # an actor configuration
uv run zanni --check examples/roles/tester              # a whole role folder
uv run zanni --check examples/scripts/software-team     # a script
uv run zanni --check examples/plays/newsroom/play.yaml  # a play, checked against its local script
uv run zanni --check examples/plays/slug-kata/play.yaml # the play you can run, below
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

## Running a play

`zanni play.yaml` starts a director that runs a whole play on your machine (D33). The repository's runnable example is the slug kata, `examples/plays/slug-kata/` (D40). A tester writes failing tests, you approve the plan, and one or two coders make the tests pass, over two rounds.

1. **Copy the examples.** The stage is a folder inside the play, and the actors write to it, so run a copy. The play refers to its script and roles by relative paths, so copy the whole `examples/` folder:
   ```bash
   cp -R examples ~/slug-kata-run
   ```
2. **Check the models.** The play folder holds the director's configuration (`director.yaml`) and one actor configuration per local seat (`tester-1.yaml`, `coder-1.yaml`, `coder-2.yaml`). Each lists its own models, in order, and nothing picks a model for you. Edit each `models` list to what you have, such as a local model with tool calling, or a cloud model and its key. The play has a $1.00 budget, so every model needs a price: a published one, or `price: { input: 0, output: 0 }` for a local model ([Models and keys](models-and-keys.md)).
3. **Set two tokens.** The join token lets actors join; the owner token lets you decide gates. Both come from the environment, never from a flag, and never reach a log:
   ```bash
   set -a; . ./.env; set +a     # your model keys, if they live in a .env
   export ZANNI_JOIN_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
   export ZANNI_OWNER_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
   ```
4. **Run it:**
   ```bash
   uv run zanni ~/slug-kata-run/plays/slug-kata/play.yaml
   ```

The director pins the script and roles in `play.lock`, lists the verifier commands it will run, starts the local seats, and follows the script. A recorded run, on `qwen3.8:27b` (trimmed paths):

```
Wrote …/plays/slug-kata/play.lock
  verifiers, run in the stage folder with your permissions:
    tests-fail: uv run --no-project --with pytest python -c import subprocess, sys; sys.exit(0 if subprocess.call([sys.executable, '-m', 'pytest', '-q', 'tests']) == 1 else 1) (from the script; timeout 300 s)
    tests-pass: uv run --no-project --with pytest python -m pytest -q tests (from the script; timeout 300 s)
Directing 'slug-kata' (slug-kata 0.1.0) at http://127.0.0.1:61086; run 20261024T202101Z
  started the local seat tester-1 (tester)
  started the local seat coder-1 (coder)
Waiting for actors to join: tester, coder
Cast coder-1 (slug-coder 0.1.0) as coder-1
Cast tester-1 (slug-tester 0.1.0) as tester-1
  cue r1-c1 to tester-1: Act 1, Scene 1: Specify — Round 1 (budget $0.5000)
  report from tester-1 on r1-c1: done, cost $0
  verifier tests-fail: passed
Gate 'plan' is waiting for a decision: zanni gate <play> approve | reject --note …
Gate 'plan' rejected by owner: Also cover an input that is only punctuation, such as '!!!', which slugifies to an empty string.
  cue r1-c2 to tester-1: Act 1, Scene 1: Specify — Round 1 (revision) (budget $0.5000)
  report from tester-1 on r1-c2: done, cost $0
  verifier tests-fail: passed
Gate 'plan' is waiting for a decision: zanni gate <play> approve | reject --note …
Gate 'plan' approved by owner: ok
  cue r1-c3 to coder-1: Act 1, Scene 2: Build — Round 1, slug (budget $0.5000)
  started the local seat coder-2 (coder)
Cast coder-2 (slug-coder 0.1.0) as coder-2
  cue r1-c4 to coder-2: Act 1, Scene 2: Build — Round 1, words (budget $0.2500)
  report from coder-1 on r1-c3: done, cost $0
  report from coder-2 on r1-c4: done, cost $0
  verifier tests-pass: passed
Round 2
  …
Released coder-1 (done)
Released coder-2 (done)
Released tester-1 (done)
The play is done. Rounds: 2; spent $0.0000; verdicts: tests-fail passed, tests-pass passed.
The play's log: …/plays/slug-kata/log/20261024T202101Z.jsonl
```

**Deciding a gate.** When the play waits at a gate, decide it from another terminal, with the same `ZANNI_OWNER_TOKEN`. On the director's own terminal you can also type `approve`, `reject <note>` or `resume`. `zanni gate` finds the running director through `log/director.json` in the play folder. Given a director's URL instead, it works from any machine that can reach it (D38). From a scripted play in the test suite:

```
$ zanni gate play.yaml
Play 'kata', run 20261024T204125Z, round 1, spent $0.0007: waiting at a gate.
  gate: plan
  The tests are written, and fail.
  Round 1. Files changed since the last gate: tests/test_slug.py. Verdicts: tests-fail passed.

$ zanni gate play.yaml approve --note go
Approved.
Play 'kata', run 20261024T204125Z, round 1, spent $0.0007: running.
```

`reject --note "…"` sends the play back with your note, and the director revises before asking again.

- **Done is checked, not claimed:** the play ends as done only when every gate the play enforces was approved, and the script's `done_when` verifiers passed on the stage as it is at the end (D33, D42). An actor saying it's done counts for nothing.
- **Exit codes:** 0 when the play is done; 1 when it stopped for any other reason (the budget, a rejected or unanswered gate, a cap, the director's own reason, or Ctrl-C); 2 when nothing could start ([Command reference](cli.md#exit-codes)).
- **Logs:** the play's log is in the play folder, under `log/`, with each local seat's output beside it. Each actor also keeps its own log under its state folder (D32).
- **The budget:** each cue gets a share of what is left, and the actor stops at it; the director's own spend counts too, after each of its model responses (D39).
- **Actors from other machines:** a part without `host: local` also takes actors joining from elsewhere, as in [Join a director on another machine](#join-a-director-on-another-machine). Start the director with `--listen 0.0.0.0:8765`, and give those actors the join token.
- **If it fails:** see [Troubleshooting](troubleshooting.md#running-a-play).

The recorded runs, on one machine with local and cloud models and on two machines, are in [docs/runs/milestone-4.md](runs/milestone-4.md).

## What works today

| Works | Not yet |
|---|---|
| Validating actor configurations, plays, scripts, lockfiles, rehearsals and whole role folders | A git stage: a play's stage is a local folder for now (milestone 5) |
| Running one actor on a rehearsal, on local or cloud models, with fallback | Renewing a seat's tokens: a seat ends when they expire, after 24 hours |
| An actor joining a director over A2A, by URL or through a play file's `director` | TLS: the director speaks plain HTTP |
| Serving a rehearsal to an actor on another machine (`--serve`), with the stage over MCP | A director that survives a restart of its process |
| Running a whole play: `zanni play.yaml` starts a director that casts local seats and joining actors, follows the script, runs its verifiers and enforces the budget | Gates per round: an enforced gate counts once per play |
| Fetching roles and scripts from git, pinned in `play.lock` | Signed tags, and version ranges |
| Deciding gates, and resuming a paused play, with `zanni gate` | Telling anyone a gate is waiting |
| Errors with their line and how to fix them; rejecting secrets in shared files | |

## Next steps

- [Concepts](concepts.md): what the pieces are and how they fit together.
- [Zanni files](files.md): every field of the three kinds of file.
- [Writing a role](writing-a-role.md): build your own role folder.
- [Writing a script](writing-a-script.md): write the work a play performs.
- [Contributing](contributing.md): if you want to work on Zanni itself.
