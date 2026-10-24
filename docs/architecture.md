# Architecture

Zanni is one Python package with one command. Today it validates Zanni files; the engine that runs actors comes later ([roadmap](../ROADMAP.md)).

## Layout

```
src/zanni/
  __init__.py       # __version__
  __main__.py       # python -m zanni
  cli.py            # the `zanni` command
  files/            # loading and validating Zanni files
    check.py        # what `zanni <path>` checks: one file, a role folder, a play against its script and lockfile
    loader.py       # YAML (or Markdown frontmatter) -> data, plus the line of every field
    errors.py       # FileError / FileErrors: the plain-words error format
    validation.py   # Pydantic errors -> plain words; secret detection; "did you mean"
    schemas.py      # Pydantic models: ActorConfiguration, PlayFile, Stage, Script, Lockfile, RoleManifest,
                    #   SkillFrontmatter, McpConfig
    kinds.py        # which kind of file this is, from its keys
    summary.py      # what a valid file would run, in a few lines
  actor/            # running an actor (no engine imports)
    contract.py     # CueTask in, CueResult out: what Zanni hands the engine, and gets back
    roles.py        # a role folder -> instructions and skills (D4)
    resolve.py      # ${NAME} from the actor's credentials, then the environment (D20); models resolved
    mcp_config.py   # a role's mcp.json, with every ${NAME} resolved
    stage.py        # the folder stage backend: operations, permissions, change markers (D12)
    rehearsal.py    # runs an actor on a rehearsal: stage copy, cues, reports, log, verify (D26)
  protocol/         # the casting extension's messages and card params, as Pydantic models (no a2a-sdk)
    encoding.py     # numbers as decimal strings: Count, Seconds, Timestamp, Money, Range (D23)
    card.py         # what each Agent Card carries in the extension's params
    messages.py     # join, cast, refused, cue, report, release, released
    fit.py          # does an actor's card fit a part: role, hash, needs within ceilings
    schemas.py      # generates docs/spec/schemas/*.schema.json
  engine/           # the engine adapter: the only code that imports Pydantic AI, mcp or a2a-sdk (D1)
    run.py          # run_cue: one cue on the actor's models, in order, with fallback and cost (D27)
    models.py       # a resolved model entry -> a Pydantic AI model
    fallback.py     # a failure -> one of D20's reasons
    text_tools.py   # the opt-in text tool format (D5)
    tools.py        # load_skill and the stage_* tools
    mcp.py          # a role's MCP servers as toolsets
    capabilities.py # asks Ollama whether a model can call tools
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
  ├─ check.resolve         a folder → its role.yaml or SCRIPT.md
  ├─ kinds.detect          role+play → ActorConfiguration, cast → PlayFile, mission → RoleManifest,
  │                        parts → Script (Markdown only), lock_version → Lockfile
  ├─ validation.validate   reject secret-looking keys; validate with the Pydantic model;
  │                        turn every ValidationError into a FileError with its line
  ├─ check.check           per kind: a play against its local script and play.lock; a role folder's
  │                        AGENTS.md, skills and mcp.json; an actor configuration's credential safeguards
  └─ summary.summarise     print what it would run          (or print every FileError, exit 2)
```

Each step raises `FileErrors` with every problem it found. `cli.main` catches it, prints each problem on standard error, and returns exit code 2.

## Key ideas in the code

- **Errors are data.** A `FileError` holds the file, the line, the field path, the problem and the fix. Its `str()` renders the documented format: `file, line N, path: problem; fix`. Nothing shows a raw Pydantic message to users.
- **Lines come from the YAML parser.** `loader.py` composes the YAML node tree and records each key's line under its field path, as a tuple such as `("cast", "coder", "seats")`. A missing field is reported at its parent's line.
- **Validators speak plain words.** A custom validator in `schemas.py` raises `ValueError("problem; fix")`. `validation.py` splits the message on the first `"; "` into the problem and the fix.
- **Strict models.** Every model inherits from `Strict` (`extra="forbid"`, frozen). For unknown keys, `validation._known_fields` walks the model tree to find the allowed names, and `difflib` suggests the closest.
- **Secrets have one home.** `find_secrets` rejects secret-looking keys anywhere, except in the sections a model lists in `SECRET_SECTIONS` (only `ActorConfiguration.credentials`). Inputs under those sections are replaced by `a value (hidden)` in every message (D15).
- **Standards are checked, not tightened.** `SkillFrontmatter` and `McpConfig` ignore fields they don't define, because SKILL.md and `mcp.json` are shared with other tools (D19).
- **Shorthand is normalised before validation.** A cast entry can be a plain package reference. A `BeforeValidator` turns it into `{role: …}`, so there is one model and error paths stay clean.

## The engine adapter

`src/zanni/engine/` is the only place that imports Pydantic AI, `mcp` and `a2a-sdk` (golden rule 4, D1). `tests/test_engine_guard.py` fails if anything else does. Zanni hands it a `CueTask` (plain data in `zanni.actor.contract`) and gets back a `CueResult`:

```
zanni slug-tester.yaml
  └─ actor.rehearsal.run_rehearsal
       ├─ actor.roles.load_role         instructions + skills (D4)
       ├─ actor.resolve.resolve_models  models with credentials and URLs resolved (D20)
       ├─ engine.models.build_model     every model built, and Ollama asked about tools, before anything runs
       ├─ actor.stage.FolderStage       a fresh stage copy, with the role's permissions
       ├─ for each cue: engine.run.run_cue(CueTask) -> CueResult
       │     an Agent with load_skill, the stage_* tools (sequential) and the role's MCP servers;
       │     on a failure, classify it and fall back if the entry lists the reason (D27)
       ├─ protocol.messages.Report      each result as a validated zanni.report; cost or null (D7)
       └─ verify commands, then the log: run-started, cue, report, cost, fallback, verdict, run-stopped
```

Joining a director over A2A comes in milestone 3.

## Dependencies

| Package | Why | Pinned |
|---|---|---|
| `pydantic` | Schemas and validation | lower bound |
| `pyyaml` | YAML parsing, with node marks for line numbers | lower bound |
| `pydantic-ai-slim[anthropic,openai,mcp]` | The agent engine (not used yet) | exact (D8) |
| `mcp` | Zanni's own MCP servers (not used yet) | exact (D8) |
| `a2a-sdk` | Director-to-actor messages (not used yet; tests round-trip the protocol through it) | exact (D8) |
| `jsonschema` (dev) | Protocol conformance against the published schemas | lower bound |
| `pytest` (dev) | Tests | lower bound |
