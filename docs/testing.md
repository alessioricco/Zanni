# Testing

```bash
uv run pytest                      # everything
uv run pytest tests/conformance    # conformance only
uv run pytest -k seats             # tests whose name matches "seats"
```

The full suite needs no API key, no network and no model. That is a hard rule: CI runs it with no secrets.

## What's where

| Path | What it tests |
|---|---|
| `tests/test_loading.py` | The loader and the plain-words errors: YAML syntax, unknown keys with suggestions, wrong types, missing fields, secrets, duplicate keys |
| `tests/test_files.py` | The `zanni` command on the examples, which must be valid, and on broken copies of them, which must fail with the right message |
| `tests/test_cli.py` | `--version` and usage |
| `tests/conformance/` | The spec: files through the `zanni` command and exit codes; casting messages through the published JSON Schemas (`test_protocol.py`) |
| `tests/test_protocol_*.py` | The protocol models: the encoding, the card fit checks, and that `docs/spec/schemas/` matches the models |
| `tests/engine/` | The engine with scripted models (`FunctionModel`): the run loop, fallback, the text tool format, MCP servers, the Ollama check; casting messages surviving `a2a-sdk`; a seat's whole life over A2A against a fake director (`test_a2a_seat.py`); the stage's MCP server and its tokens (`test_stage_mcp.py`) |
| `tests/test_actor_*.py`, `tests/test_rehearsal.py` | Roles, credential resolution, the stage's permission layer (against the local folder and the MCP server, through `tests/stage_over_mcp.py`), an actor joining a director over loopback, a cue that meets a stage gone away, and a whole rehearsal with a scripted model |
| `tests/test_stage_backends.py` | The same tests on every backend in `BACKENDS` (`folder`, `git`, `mcp` on the example SQLite stage server): operations, errors, the record of changes, snapshots |
| `tests/test_git_stage.py`, `tests/test_mcp_stage.py` | A play on a git stage (a bare remote in `tmp_path`: commits by seat, pushes under each `push` setting, a run stopped by hand, a push that fails, a remote that can't be cloned) and on an `mcp` stage (a wrong token, the server going away and coming back, a server that doesn't take `author` and `note`) |
| `tests/test_verifier_seats.py` | Verifiers on a snapshot, verifier seats: their token, which seats are trusted, the exit code as the verdict |
| `tests/test_director.py` | The director's casting side on its own: every refusal, tokens, cues and reports, release, heartbeats on a fake clock |
| `tests/test_join.py`, `tests/test_serve.py` | Joining by URL or play file from an actor configuration, `--serve` in another process, and a director stopping while an actor's task stream is open |
| `tests/test_fetch.py` | Fetching packages with git and `play.lock`, against bare repositories in `tmp_path` reached through git's own `url.insteadOf`, with no network |
| `tests/test_director_rules.py`, `tests/test_verifiers.py` | The director's rules in code, the host cap, changes per seat, and running verifiers |
| `tests/test_director_agent.py` | The director's agent with a scripted model against scripted actors over loopback (`tests/director_harness.py`): a play end to end, refusals, the turn cap, a pause |
| `tests/test_casting_play.py` | Local seats as real `zanni` subprocesses, recasting, pricing at join, a cue's budget, reservations |
| `tests/test_gates.py`, `tests/test_gates_per_round.py` | `zanni gate` against a director on loopback, tokens, a gate timeout, the console; gates every round and before a part's cues |
| `tests/test_play_command.py`, `tests/test_slug_kata.py`, `tests/test_example_plays.py` | `zanni play.yaml` in another process, every exit code, a director killed with `-9`, a part or verifier seat nobody takes; the slug kata, the slug kata on git and release notes on the example stage server, end to end from a copy of `examples/` |
| `tests/fake_openai.py` | Not a test: a tiny OpenAI-compatible server on loopback, so real `zanni` subprocesses can play a director or a seat with no model and no network |
| `tests/conftest.py` | Not a test: fails the session if any test changed `examples/` |
| `tests/test_tool_bindings.py`, `tests/test_workspace.py` | Tools an actor brings: a binding replacing a role's server, its price per call in a cue's cost and budget, an unpriced one refused at join, a server that won't start; the workspace: its server's tools, `run` limited to `workspace.commands`, paths that can't leave the folder, filling and sending back on every backend, a cue's paths, `.gitignore`, and an actor with a workspace over loopback |
| `tests/test_check_files.py`, `tests/engine/test_model_settings.py` | The software script's check files on crafted folders, a check file run beside the snapshot and on a verifier seat; the director's prompt caching and `max_output` at the engine's door |
| `tests/test_software_roles.py`, `tests/test_software_play.py`, `tests/test_continuing.py` | Each of the six roles' rehearsals; one round of the software script end to end with all six parts scripted; another round at a gate, and a run continued on git |
| `tests/test_engine_guard.py` | Only `src/zanni/engine/` imports Pydantic AI, `mcp`, `a2a-sdk` and their providers |
| `tests/live/` | A real rehearsal on a real model; skipped unless `ZANNI_LIVE_CONFIG` names an actor configuration |

## Conformance tests

The conformance suite checks an implementation of the `zanni` command against the [spec](spec/README.md). It doesn't import Zanni's code, so it can test any implementation.

- **`valid/*.yaml`:** each must exit `0`.
- **`invalid/*.yaml`:** each must exit `2`, and report a problem at the line and field path in its `.expected` sidecar:

  ```
  line: 4
  path: cast.coder.seats
  ```

  An empty value means "anywhere", for problems with no single field.

To test another implementation, set `ZANNI_CMD`:

```bash
ZANNI_CMD="/path/to/other-zanni" uv run pytest tests/conformance
```

To add a case:

1. Add one small file that tests one rule.
2. Name it after the rule, such as `play-seats-reversed.yaml`.
3. For an invalid file, add its `.expected` sidecar.

A spec change and its conformance cases go in the same commit (golden rule 2).

For casting messages, add a JSON file to `tests/conformance/protocol/valid/` or `invalid/`; an invalid one gets a `.expected` sidecar with the JSON pointer of the error (`path: /limits/budget/amount`). Another implementation's messages can be checked with `ZANNI_PROTOCOL_DIR=<folder>`. After changing `src/zanni/protocol/`, regenerate the schemas with `uv run python -m zanni.protocol.schemas`.

## Writing tests

- **Message tests:** test the user-facing message, not internals. A test like `test_broken_copies_fail_in_plain_words` runs the real command on a real file and checks the exact text users see.
- **Examples stay valid:** `test_examples_validate` fails if a schema change breaks one.
- **No real model in the suite.** Use `tests/engine/fakes.py`: `MemoryStage`, and `scripted(...)`, a `FunctionModel` that plays tool calls, replies or exceptions in order, and records what it was sent. For a director, `tests/director_harness.py` has `Steps`; for a `zanni` subprocess, point its configuration at `tests/fake_openai.py`, whose model names say what it does.
- **Examples are run from copies.** A play's stage is its own folder, so tests copy `examples/` to `tmp_path` first; `tests/conftest.py` fails the run if `examples/` changed.
- **Git and stage servers stay local.** Git tests use bare repositories in `tmp_path`, and `mcp` tests run the example stage server on loopback: nothing reaches the network.
- **Live tests** skip with a clear message when no model is configured:

  ```bash
  ZANNI_LIVE_CONFIG=~/zanni/slug-tester.yaml uv run pytest tests/live
  ```

  They never replace recorded runs as the proof of a claim (golden rule 7). Recorded runs are in `docs/runs/`.

## CI

`.github/workflows/test.yml` runs `uv sync --locked` and `uv run pytest` on Python 3.12 and 3.14, for every push and pull request. `UV_PYTHON` is set for the whole job, so the conformance tests' `uv run zanni` runs on the same Python as the test run. The workflow uses no secrets.

To run the suite on another Python version locally, without touching your main environment:

```bash
UV_PYTHON=3.12 UV_PROJECT_ENVIRONMENT=/tmp/zanni-py312 sh -c 'uv sync --locked && uv run pytest'
```
