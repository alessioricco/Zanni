# Architecture

Zanni is one Python package with one command. It validates Zanni files, runs actors that join a director over A2A, serves rehearsals, and runs a whole play: a director that follows a script, casts actors (local seats it starts, and remote ones that join), and enforces the rules in code (D33).

## Layout

```
src/zanni/
  __init__.py       # __version__
  __main__.py       # python -m zanni
  cli.py            # the `zanni` command
  gate.py           # `zanni gate`: the owner's client for a running director (D38)
  commands.py       # running a verifier's command in a snapshot, its process group killed on a timeout (D35, D45)
  fetch.py          # remote packages: a tag, fetched with git into ~/.zanni/packages (D37)
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
    seat.py         # an actor in a play: the director's card, its own card, join, cues, reports, release (D30)
    join.py         # where to join (a URL or a play file's director), and the set-up rehearsals share
    rehearsal.py    # an actor on a rehearsal, with a director started for it on loopback (D26, D29)
    verifier.py     # a verifier seat: pull a snapshot over MCP, run the command, answer the exit code (D45)
    verifier_role/  # the built-in zanni:verifier role
  director/         # the director (engine imports only inside command.py and rehearsal.py's functions)
    contract.py     # Casting: what the engine's A2A server asks of the director; Outgoing, DirectorInfo
    casting.py      # Director: joins and refusals, seats and tokens, cues and reports, heartbeats, release
    rehearsal.py    # a rehearsal's one part, conducting its cues, verify, and --serve (D29)
    command.py      # `zanni play.yaml`: checks before anything starts, serving, local seats, turns, the end
    packages.py     # a play's script and roles against play.lock (D37)
    state.py        # the play's state, kept in code: rounds, spend, reservations, verdicts, gates (D33)
    rules.py        # the rules each tool checks first: budget, done, verifiers, casting, rounds (D33, D39)
    play.py         # Production: the director's tools, the state summary of each turn, the turn loop
    prompt.py       # the director's instructions: its role, the parts, the rules, the script's prose
    role/           # the built-in zanni:director role (role.yaml, AGENTS.md) (D34)
    gates.py        # gates and pauses wait for a person's decision, or gate_timeout (D38)
    owner.py        # who may decide (the owner token), and what a decision does
    console.py      # the same decisions typed in the director's terminal
    local.py        # local seats: `zanni <config> --play <url>` subprocesses on a pipe (D36)
  stage/            # the stage (no engine imports) (D43)
    layer.py        # Stage and SeatStage: paths, each seat's permissions, the record of changes, snapshots
    backend.py      # StageBackend: what a backend must do (storage only)
    folder.py       # the folder backend
    git.py          # the git backend: a clone, a branch per run, a commit per write, pushes (D46)
    paths.py        # stage paths: relative, `/`, never leaving the stage
    errors.py       # StageError and its codes
  log.py            # the JSON Lines logs: the play's and each actor's own (D18, D32)
  protocol/         # the casting extension's messages and card params, as Pydantic models (no a2a-sdk)
    encoding.py     # numbers as decimal strings: Count, Seconds, Timestamp, Money, Range (D23)
    card.py         # what each Agent Card carries in the extension's params
    messages.py     # join, cast, refused, cue, report, release, released, verify, verdict
    fit.py          # does an actor's card fit a part: role (or a local role's name), hash, needs within ceilings
    schemas.py      # generates docs/spec/schemas/*.schema.json
  engine/           # the engine adapter: the only code that imports Pydantic AI, mcp or a2a-sdk (D1)
    run.py          # run_cue: one cue on the actor's models, in order, with fallback, cost, and the cue's budget
    director_agent.py # one director turn on its models, with its tools and fallback (D33)
    pricing.py      # whether a model has a price, published or declared (D39)
    models.py       # a resolved model entry -> a Pydantic AI model
    fallback.py     # a failure -> one of D20's reasons
    text_tools.py   # the opt-in text tool format (D5)
    tools.py        # load_skill and the stage_* tools
    mcp.py          # a role's MCP servers as toolsets
    capabilities.py # asks Ollama whether a model can call tools
    a2a_wire.py     # casting messages in and out of A2A messages, validated both ways
    a2a_server.py   # the director's card, a task per seat, the token on every call (D21, D31)
    a2a_client.py   # the actor's side: fetch the card, join, follow the task (stream, then polling)
    stage_mcp.py    # the stage's MCP server (Streamable HTTP, a token per seat), and RemoteStage
    stage_backend.py # the mcp backend: any MCP server with the five stage tools, retried and reconnected (D47)
    serve.py        # serves a Director: A2A, the stage's MCP server and the owner's endpoint, plus the heartbeat watch
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
- **The director decides, the engine carries.** The engine's A2A server never decides who is cast or what a seat does next: it calls the `Casting` interface (`director/contract.py`), which `director/casting.py` implements. A play's director drives that same casting side through `Production`.
- **The model chooses, code allows.** The director's model picks its next action, but each tool (`director/play.py`) calls the plain rules in `director/rules.py` first, and answers a refusal in plain words instead of acting. The engine (`engine/director_agent.py`) only runs the model loop with those tools (D33).
- **One stage tool set.** The actor's `stage_*` tools are the same code for a seat's view on the director's side (`SeatStage`) and a `RemoteStage` over MCP, and the remote stage turns tool errors back into the same `StageError`. So a model sees the same tools and errors either way.
- **One permission layer, many backends.** `stage.layer.Stage` sits above every backend: it checks paths and each seat's permissions, takes one write at a time, and keeps the record of who changed what, whose positions are the change markers seats see. A backend (`folder`, `git`, `mcp`) only stores text, so a new backend can't loosen a permission (D43).
- **Shorthand is normalised before validation.** A cast entry can be a plain package reference. A `BeforeValidator` turns it into `{role: …}`, so there is one model and error paths stay clean.

## The engine adapter

`src/zanni/engine/` is the only place that imports Pydantic AI, `mcp` and `a2a-sdk` (golden rule 4, D1). `tests/test_engine_guard.py` fails if anything else does. Zanni hands it a `CueTask` (plain data in `zanni.actor.contract`) and gets back a `CueResult`.

## An actor and a director

```
zanni actor.yaml                                   zanni smoke.yaml --serve        (or both in one process,
  └─ actor.join.join_play                            └─ director.rehearsal              for a rehearsal)
       ├─ the director's URL (D30)                         ├─ the stage, copied fresh
       ├─ ready_actor: role, models, built and checked     ├─ Director: one part, the role's name and hash
       └─ actor.seat.play_seat                              └─ engine.serve.serving
            ├─ engine.a2a_client: fetch the card ───────────▶ engine.a2a_server: the card
            ├─ join with the actor's card + join token ─────▶ Director.join: token, card, fit, seats → zanni.cast
            ├─ engine.stage_mcp.remote_stage ───────────────▶ engine.stage_mcp: the stage's MCP server
            ├─ follow the task (stream; polling) ◀─────────── director.rehearsal.conduct: each zanni.cue
            ├─ each cue: engine.run.run_cue → zanni.report ─▶ Director.report
            └─ zanni.release → zanni.released ──────────────▶ Director.release; then verify
```

- **Two logs:** the director keeps the play's log (`log.jsonl`); the actor keeps its own, on its own machine (D32).
- **Contact:** the director's heartbeat watch ends a seat that has had no contact for `misses × interval`, with an open stream counting as contact (D31), and revokes its tokens.

## A play

```
zanni play.yaml   (or zanni director.yaml)
  └─ director.command.run_play
       ├─ the director's configuration (--director, or director.yaml beside the play)        (D34)
       ├─ director.packages: script and roles, fetched or local, checked against play.lock   (D37)
       ├─ the play against its script; the director's models, priced under a budget; its join,
       │  owner and verifier tokens; the stage opened (a folder, a git clone, or the stage
       │  server reached with ZANNI_STAGE_TOKEN), holding stage.expects ── any problem: exit 2, nothing started
       ├─ engine.serve.serving: A2A + the stage's MCP server + /zanni/owner; log/director.json
       ├─ director.local: start each part's minimum of local seats, and the local verifier seats ──▶ zanni <config> --play <url>
       ├─ wait for every part's minimum seats, and every verifier seat a verifier runs_on,
       │  within cast_timeout; otherwise stop: uncastable                                  (D50)
       ├─ Production.direct: turns until the play stops
       │    each turn: engine.director_agent.run_director_turn(the state summary, the tools)
       │      cue / wait_for_reports / run_verifier / ask_gate / cast / release / end_round / stop
       │      └─ each tool: director.rules first, then director.casting, the stage, the gates
       │    a turn ends after each long wait: reports, or a gate                              (D49)
       │    every model failed, or the stage server is away: pause until `zanni gate … resume` (D33, D47)
       ├─ Production.finish: release every seat, stop the local seats; run-stopped; exit 0 or 1
       └─ a git stage: push the run's branch, or print how to publish it                     (D46)
```

- **A cue's life:** `cue` reserves its budget and sends it through the casting side; a follower waits for the report, charges its cost, and takes its changes from the stage's record (D41). A seat lost mid-cue is recast, and the cue resent (D36).
- **The director's own spend:** `run_director_turn` tells `Production.director_spending` the turn's spend after each model response, before its tool calls run; it counts in the play's spend at once, and the turn ends when the budget is reached (D39).
- **Gates:** `ask_gate` waits on `director.gates`, which only the owner's endpoint or the console resolves; actors have no way to it (D38). A gate may be asked every round, and its `before` parts can't be cued until it is approved in that round (D48).
- **Verifiers:** `run_verifier` takes a snapshot of the stage into a fresh folder and runs the command there (`zanni.commands`), or sends it to the verifier seat the verifier `runs_on` as `zanni.verify`, and takes the exit code from `zanni.verdict` (D45).

## Dependencies

| Package | Why | Pinned |
|---|---|---|
| `pydantic` | Schemas and validation | lower bound |
| `pyyaml` | YAML parsing, with node marks for line numbers | lower bound |
| `pydantic-ai-slim[anthropic,openai,mcp]` | The agent loop, model providers, cost, and a role's MCP servers | exact (D8) |
| `mcp` | The stage's MCP server, the actor's client for it (D31), and the `mcp` backend's client (D47) | exact (D8) |
| `a2a-sdk[http-server]` | The director's A2A server and the actor's client (D21) | exact (D8) |
| `uvicorn` | Serves the director (already required by `mcp`) | lower bound |
| `jsonschema` (dev) | Protocol conformance against the published schemas | lower bound |
| `pytest` (dev) | Tests | lower bound |
