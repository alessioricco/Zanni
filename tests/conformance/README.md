# Conformance tests

These tests check an implementation of the `zanni` command against the [spec](../../docs/spec/README.md), using only files and exit codes. They don't depend on this codebase.

- **`valid/`:** every case must be accepted, with exit code `0`. A case is a `.yaml` file, a `.md` file (such as a script), or a folder (such as a role package or a script folder).
- **`invalid/`:** every case must be rejected, with exit code `2`. Its `.expected` sidecar (`name.expected` for `name.yaml`, `name.md` or the folder `name/`) gives the problem the implementation must report:
  ```
  line: 4
  path: cast.coder.seats
  ```
  At least one line of the implementation's error output must contain `line <n>` (as a whole number) and ` <path>:`. An empty value means "anywhere", which is used for problems with no single field, such as a file that isn't a Zanni file. This matches the spec's error format: file, line, field path, what is wrong, what to change.

## Running them

Against this implementation:

```bash
uv run pytest tests/conformance
```

Against another implementation, set `ZANNI_CMD` to the command that runs it. It is called as `$ZANNI_CMD --check <file>`, so that a valid actor configuration is validated, never run (D28):

```bash
ZANNI_CMD="/path/to/other-zanni" uv run pytest tests/conformance
```

## Adding a case

1. Add a small file that tests one rule from the spec.
2. Name it after that rule, such as `play-seats-reversed.yaml`.
3. For an invalid file, add its `.expected` sidecar.

A spec change and its conformance cases go in the same commit (golden rule 2).

## Protocol conformance

`test_protocol.py` checks casting messages (`docs/spec/casting-extension.md`) against the published JSON Schemas in `docs/spec/schemas/`. It uses no Zanni code, only the schemas and the examples.

- **`protocol/valid/*.json`:** each must pass the schema named by its `kind`, such as `zanni.cast.schema.json`.
- **`protocol/invalid/*.json`:** each must fail. Its `.expected` sidecar gives the JSON pointer of an error the schema must report, such as `path: /limits/budget/amount`. An empty path means the message itself, as for a missing or unknown field.

To check another implementation's messages, put them in a folder laid out the same way and point `ZANNI_PROTOCOL_DIR` at it:

```bash
ZANNI_PROTOCOL_DIR=/path/to/their/messages uv run pytest tests/conformance/test_protocol.py
```

The schemas are generated from `src/zanni/protocol/`; `tests/test_protocol_schemas.py` fails if they drift. `tests/engine/test_a2a_roundtrip.py` proves that every valid example survives `a2a-sdk` unchanged (D23).
