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
| `tests/engine/` | The engine with scripted models (`FunctionModel`): the run loop, fallback, the text tool format, MCP servers, the Ollama check; and casting messages surviving `a2a-sdk` |
| `tests/test_actor_*.py`, `tests/test_rehearsal.py` | Roles, credential resolution, the folder stage, and a whole rehearsal with a scripted model |
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
- **No real model in the suite.** Use `tests/engine/fakes.py`: `MemoryStage`, and `scripted(...)`, a `FunctionModel` that plays tool calls, replies or exceptions in order, and records what it was sent.
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
