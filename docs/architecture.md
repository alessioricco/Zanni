# Architecture

Zanni is one Python package with one command. Today it validates Zanni files; the engine that runs actors comes later ([roadmap](../ROADMAP.md)).

## Layout

```
src/zanni/
  __init__.py       # __version__
  __main__.py       # python -m zanni
  cli.py            # the `zanni` command
  files/            # loading and validating Zanni files
    loader.py       # YAML -> data, plus the line of every field
    errors.py       # FileError / FileErrors: the plain-words error format
    validation.py   # Pydantic errors -> plain words; secret detection; "did you mean"
    schemas.py      # Pydantic models: ActorFile, PlayFile, RoleManifest
    kinds.py        # which kind of file this is, from its keys
    summary.py      # what a valid file would run, in a few lines
  engine/           # the engine adapter (empty for now)
examples/           # one valid file of each kind
tests/              # unit tests, CLI tests
tests/conformance/  # data-driven tests that any implementation can run
docs/               # user and contributor docs; docs/spec/ is the spec
scripts/            # get-skills.sh
```

## How a file flows through `zanni`

```
zanni play.yaml
  │
  ├─ loader.load_file      read the text; parse the YAML; map every field path to its line;
  │                        reject duplicate keys and YAML syntax errors
  ├─ kinds.detect          role+play → ActorFile, cast → PlayFile, mission → RoleManifest
  ├─ validation.validate   reject secret-looking keys; validate with the Pydantic model;
  │                        turn every ValidationError into a FileError with its line
  └─ summary.summarise     print what it would run          (or print every FileError, exit 2)
```

Each step raises `FileErrors` with every problem it found. `cli.main` catches it, prints each problem on standard error, and returns exit code 2.

## Key ideas in the code

- **Errors are data.** A `FileError` holds the file, the line, the field path, the problem and the fix. Its `str()` renders the documented format: `file, line N, path: problem; fix`. Nothing shows a raw Pydantic message to users.
- **Lines come from the YAML parser.** `loader.py` composes the YAML node tree and records each key's line under its field path, as a tuple such as `("cast", "coder", "seats")`. A missing field is reported at its parent's line.
- **Validators speak plain words.** A custom validator in `schemas.py` raises `ValueError("problem; fix")`. `validation.py` splits the message on the first `"; "` into the problem and the fix.
- **Strict models.** Every model inherits from `Strict` (`extra="forbid"`, frozen). For unknown keys, `validation._known_fields` walks the model tree to find the allowed names, and `difflib` suggests the closest.
- **Shorthand is normalised before validation.** A cast entry can be a plain role reference. A `BeforeValidator` turns it into `{role: …}`, so there is one model and error paths stay clean.

## The engine adapter (coming)

`src/zanni/engine/` will be the only place that imports Pydantic AI, `mcp` and `a2a-sdk` (golden rule 4, D1). It will contain:

- **Roles:** loading `AGENTS.md` and skills on demand (D4).
- **Models:** building a model from the host's model list, with the opt-in text tool format for models without native tool calling (D5).
- **Tools:** loading a role's `mcp.json` (D3).
- **A2A:** serving an actor's Agent Card and cues over the official `a2a-sdk` (D2, D6).
- **Cost:** cost per run, where an unknown cost stays unknown (D7).

The [spike report](spikes/pydantic-ai.md) shows a working prototype of each part.

## Dependencies

| Package | Why | Pinned |
|---|---|---|
| `pydantic` | Schemas and validation | lower bound |
| `pyyaml` | YAML parsing, with node marks for line numbers | lower bound |
| `pydantic-ai-slim[anthropic,openai,mcp]` | The agent engine (not used yet) | exact (D8) |
| `mcp` | Zanni's own MCP servers (not used yet) | exact (D8) |
| `a2a-sdk` | Director-to-actor messages (not used yet) | exact (D8) |
| `pytest` (dev) | Tests | lower bound |
