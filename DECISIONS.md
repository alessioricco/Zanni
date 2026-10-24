# Decisions

Each decision says what was decided, why, and what would make us revisit it. Newest last. A decision is changed by adding a new one that supersedes it, not by editing the old one.

## D0. Foundations (2026-10-22)

- **Python 3.12+ and uv**, with one entry point: `zanni <file>.yaml`. Rust was considered and set aside for now.
- **MIT licence.**
- **Name:** "Zanni", held on PyPI (0.0.1 placeholder) and at `github.com/alessioricco/Zanni`.
- **Standards first:** AGENTS.md, skills in the SKILL.md format, MCP, A2A, and the A2A Agent Card. Zanni specifies only the gaps.

## D1. Pydantic AI is the agent engine (2026-10-23)

**Decision:** actors run their agent loop on Pydantic AI (`pydantic-ai-slim`), behind Zanni's engine adapter. Roles, plays, actor files and protocol messages never mention it.

**Why:** it is independent of any model vendor and has the largest community. The spike (`docs/spikes/pydantic-ai.md`) gave a go:

- the same actor ran on `qwen3.8:27b` (Ollama) and `claude-haiku-5-5` with no code change;
- a role's standard `mcp.json` loaded with no client code;
- cost per run and a cost limit are built in for priced models;
- every gap was filled from outside Pydantic AI (wrappers, toolsets), without patching or forking it.

**Considered and set aside:**

- the OpenHands SDK: built and tuned for coding agents;
- Strands Agents: the closest feature match, but leans towards AWS;
- Google ADK: leans towards Gemini.

**Conditions:**

- Pin the Pydantic AI version (2.60.0 at the time of the spike), and upgrade only when the conformance tests pass. The API is large and changes fast.
- Set `PYDANTIC_AI_NO_BANNER=1` in the engine, or Pydantic AI prints a promotional banner on every run.

**Revisit if:** Pydantic AI starts requiring a vendor; the adapter needs to patch its internals; or upgrades break conformance repeatedly.

## D2. A2A through the official `a2a-sdk`, not FastA2A (2026-10-23)

**Decision:** director-to-actor messages use the official `a2a-sdk` (1.2.3 at the spike).

**Why:** Pydantic AI 2.60 has no A2A support of its own. FastA2A is a separate implementation, now at `github.com/datalayer/fasta2a`, and doesn't use `a2a-sdk`. The Agent Card and the casting extension are part of Zanni's spec, so Zanni keeps them on the reference SDK. That costs about 25 lines of executor code.

**Notes:**

- The a2a client's default HTTP timeout is 5 s. Cues must be A2A tasks with polling or streaming, not one long blocking request.

## D3. MCP: standard `mcp.json`, two implementations in play (2026-10-23)

**Decision:** a role declares its MCP servers in `mcp.json`, in the standard `mcpServers` format. The engine loads them with Pydantic AI's `load_mcp_toolsets`. MCP servers that Zanni ships, such as verifiers, use the official `mcp` SDK.

**Why:** the format is shared with Claude Desktop, Claude Code and Cursor, and needs no Zanni code to load. Pydantic AI's MCP client is built on FastMCP rather than the official SDK. The two worked together over stdio in the spike.

**Notes:**

- The conformance tests must include a server built on the official SDK.

## D4. Skills load on demand (2026-10-23)

**Decision:** the actor's instructions are the role's `AGENTS.md`, followed by each skill's name and description. A `load_skill` tool returns a skill's full body when the model asks for it.

**Why:** Pydantic AI has no AGENTS.md or SKILL.md support. Loading on demand keeps the context small. In the spike, both models loaded the skill unprompted in every full run.

## D5. Text-based tool fallback: opt-in, as a wrapper model (2026-10-23)

**Decision:** models without native tool calling are supported through an opt-in wrapper model, enabled per model entry with `tool_format: text`. The wrapper describes the tools in the prompt and parses tool-call blocks out of the reply. Cloud models and models with native tool calling never go through it.

**Why:**

- Pydantic AI has no fallback. A request with tools fails with HTTP 400 on such a model, and Pydantic AI's model profile wrongly reports tool support.
- A 64-line `WrapperModel` worked with no change to the agent loop, the toolsets or the scope checks.
- This follows golden rule 6: local first, cloud never worse.

**Still to do:** several calls in one reply, repair of malformed blocks, streaming, and conformance runs on several small models. Detecting what a local model server supports (for example Ollama's `/api/show`) comes with it, so a missing capability is caught before a run.

## D6. Role fields travel in an Agent Card extension (2026-10-23)

**Decision:** when an actor joins, its Agent Card carries the role's needs, never-rules and model needs in an A2A extension (`AgentCapabilities.extensions`). The director casts against that extension. The extension URI is provisional until the spec is written.

**Why:** the spike showed nested lists and dicts survive intact. A2A has no other place for these fields.

**Caveat:** extension params are a protobuf `Struct`, which has no integer type, so numbers arrive as floats. The spec must define a typed encoding for counts and money, for example decimal strings, and validate it when an actor joins.

## D7. Cost: unknown is never zero (2026-10-23)

**Decision:**

- A seat's cost comes from Pydantic AI's `usage.cost` (genai-prices) when the model is priced.
- Otherwise it comes from a price per million tokens declared by the actor's host in its `models.yaml`, which may be 0 for local hardware.
- Otherwise the cost is reported as unknown.
- The director treats an unknown cost as unsafe for the budget: it requires a declared price, or a token budget, before it casts that seat.

**Why:**

- genai-prices has no Ollama prices, and Pydantic AI then reports `None` without any warning.
- `cost_limit` can't stop a run on an unpriced model; it only warns.
- `cost_limit` is checked after each response, so the request that crosses the limit has already been paid for.

The budget therefore lives in the director, across seats, as the trust model says. Pydantic AI's per-run limit is not enough.

## D8. Exact pins for the engine's dependencies (2026-10-23)

**Decision:**

- `pydantic-ai-slim[anthropic,openai,mcp]`, `mcp` and `a2a-sdk` are pinned to exact versions in `pyproject.toml`: 2.60.0, 2.3.0 and 1.2.3, the versions the spike tested.
- `pydantic` and `pyyaml` have lower bounds only.
- `uv.lock` is committed.

**Why:** all three engine packages change fast, and D1 allows an upgrade only when the conformance tests pass. An exact pin makes every upgrade a deliberate change, with its own commit and test run.

**Revisit if:** Zanni is installed as a library next to other packages that need different versions of these.

## D9. The kind of file is detected from its keys (2026-10-23)

**Decision:** `zanni <file>` works out what it was given from the keys in the file, never from a flag or the file name:

- `role` and `play` make an actor file;
- `cast` makes a play file;
- `mission` makes a role manifest.

A file that matches no kind, or more than one, is an error that names the keys each kind needs. A key that is close to one of those markers, such as `mision`, gets a "did you mean" instead.

**Why:** "one command, one file" and "flags only override". File names are the user's own choice, so they can't carry meaning.

**Revisit if:** a new kind of file has no distinctive key. It would then need an explicit `kind:` field, which would be a spec change.

## D10. Unknown keys and secrets are rejected, in plain words (2026-10-23)

**Decision:**

- Every Zanni file is validated strictly: an unknown key is an error, with "did you mean" when a known key is close.
- Every problem in a file is reported at once, each with its file, line, field path, what is wrong and what to change. Raw Pydantic messages are never shown.
- A key that looks like a secret, at any depth, is rejected, and the message points to the environment or `.env`.
- A key looks like a secret when one of its words is `key`, `apikey`, `token`, `secret`, `password` or `passwd`. Words are split on `_`, `-` and camelCase, so `api_key`, `apiKey` and `client_secret` match, and `keywords`, `monkey` and `tokenizer_model` don't.
- A duplicate key is an error. PyYAML would silently keep the last one.

**Why:**

- Typos in a permissive schema become silent defaults, which is a trust problem: a misspelled `house_rules` key must never loosen a limit.
- "No secrets in files" is enforced by the parser, not by goodwill (golden rule 5).

**Revisit if:** files need extension fields from other tools. They would get a reserved prefix, such as `x-`, rather than loosening strictness.

## D11. The actor's model is set in its configuration (2026-10-23)

**Decision:**

- An actor's configuration lists the models it runs, in order. The first is used; the next one is used when it fails.
- The role never forces a model. Its `model.needs` and `suggested` are hints for whoever writes the configuration.
- The script and the play never choose models.

**Why:** Alessio's call. A zanni is an empty shell. Its role package says what it can do, and its configuration says how this instance runs, including which model. A remote actor contributes with its own model.

**Consequence:** the director can't verify which model an actor used. Quality is enforced by verifiers on the director's side, never by model choice.

**Supersedes:** D7's "a price declared by the actor's host in its `models.yaml`". The price now lives in the model entry of the actor's configuration.

**Closes:** the vision's open question "Who chooses the model".

## D12. The stage is an abstract workspace (2026-10-23)

**Decision:**

- The spec defines the operations every stage offers, and the permissions for each seat.
- The play chooses a backend, and the backend enforces the permissions.
- The first version specifies two backends:
  - `git`: a branch per seat, for plays whose work is code;
  - one non-git backend, the simplest that proves the abstraction, for plays whose work is documents.

**Why:** Alessio's call. A stage is a git repository only when the play is about code; a play that writes a document may need something else.

**Closes:** the vision's open question "Stage". It replaces "a stage as a git repo" in the first version's scope.

## D13. Script and play are separate (2026-10-23)

**Decision:**

- **The script** is the reusable work: the mission, the parts it needs, the workspace it expects, and how the work unfolds. It is published and referenced like a role (`host/owner/name@version`), and may suggest a role for each part.
- **The play** is one production of a script: the director, a role cast into each part within the script's limits, the stage, and the house rules.
- **Kinds of file:** the play file references its script with `script:`, which is required, and casts the script's parts in `cast:`. D9's marker for a play file stays `cast`, so a play without `script:` is reported as "script is required" rather than as an unknown kind of file.

**Why:** Alessio's call, after the theatre itself: two companies can stage the same script with different actors and directors, as *Hamilton* runs on Broadway and in the West End.

**Format:** the script's format must stay flexible, because scripts solve very different problems. It is specified in `docs/spec/script.md`.

## D14. Configuration is separate from the role (2026-10-23)

**Decision:**

- **The actor configuration** is one instance's file: its name, its role reference, the play it joins, its models and its credentials.
- **The role package** holds only capabilities: character, skills, tools, needs. It never holds a name, a model choice or a credential.
- **Files:** what was the "actor file" is now the actor configuration.

**Why:** the same role package runs as many actors, on different machines, with different models and access. Mixing instance settings into the role would make every instance a fork.

## D15. The actor configuration may hold its credentials (2026-10-23)

**Decision:** an actor configuration may hold that instance's credentials: API keys for its models, and tokens or key paths for its tools. `zanni` protects them:

- **Permissions:** a configuration holding credentials is refused if other users can read it (anything looser than `600`), as SSH does with private keys. The message gives the `chmod` to run.
- **Git:** it is refused if git tracks it inside a repository. Git-ignored files are fine.
- **Output:** credentials are never printed, logged or sent to the director. Summaries show them as `••••`.
- **Indirection:** a credential may instead be `${VAR}`, read from the environment, which is useful in CI.

Roles, scripts and plays still reject anything that looks like a secret (D10). Those files are shared and published.

**Why:** Alessio's call. The configuration is an instance file, like an addressable `.env` for one actor, and never part of a repository. Two actors on one machine need different credentials: one uses OpenAI and one Claude, one has GitHub access and one an SSH terminal. A `.env` bound to a codebase can't express that.

**Supersedes:** D10's "no Zanni file holds a secret", for the actor configuration only. The agent-session rule is unchanged: never print, log or commit a real key, and tests use obviously fake keys.

**Not in the first version:** secrets management for actors running on cloud services.

## D16. Actors reach the stage through MCP; git stages also allow a checkout (2026-10-23)

**Decision:**

- **Every backend:** the director serves the stage as an MCP server with five tools, `stage_read`, `stage_write`, `stage_list`, `stage_delete` and `stage_changes`. Each seat's credentials are scoped to it, given at casting and revoked at release, and the server applies the seat's permissions on every call.
- **Git backends:** a seat may also clone the repository and push to its own branch. The director merges the branch only if every changed path is within the seat's write permissions.
- **Who gets a clone:** direct access is offered only to seats whose read permissions cover the whole stage, because a clone can't hide files.

**Why:**

- Zanni needs only MCP (golden rule 3), and actors already reach every tool that way.
- Coding engines work on a real checkout, so git plays need one.
- Checking before merging keeps write permissions enforced by the stage, not by the actor.

**Considered:**

- **MCP only:** coding engines couldn't use a checkout.
- **Each backend's own protocol:** a different client for every kind of stage.

Approved by Alessio at ask point A.

## D17. A script is Markdown with a small frontmatter (2026-10-23)

**Decision:** a script is `SCRIPT.md`, styled like `SKILL.md`:

- **Frontmatter:** YAML frontmatter holds only what must be checked: `name`, `version`, `mission`, `parts` (with seats, read and write ceilings, an optional suggested role, and whether the part is optional), the paths the stage must hold, the gates, and the stop rules.
- **Prose:** acts, scenes, cues, hand-offs and verifiers are prose for the director.
- **Validation:** `zanni` validates the frontmatter strictly, and checks only that the prose is present.

**Why:**

- The director is an agent, and scripts must fit very different work (a software team, a newsroom, a writers' room) without new fields.
- Markdown with frontmatter is the convention Zanni already uses for skills (SKILL.md) and roles (AGENTS.md).

**Standards checked:**

- **[CNCF Serverless Workflow](https://github.com/serverlessworkflow/specification):** a DSL of typed tasks (call, do, fork, switch, listen, emit) for runtimes that execute exactly.
- **[Arazzo](https://spec.openapis.org/arazzo/latest.html)** (OpenAPI Initiative): sequences of API calls.

Both describe deterministic workflows run by machines, not work interpreted by an agent, and neither fits a script whose steps are judgement calls. Neither is used.

**Considered:** a fully structured YAML script, with every scene, cue and verifier as fields. It is more checkable, but rigid, and it would need new fields for every new kind of work.

Approved by Alessio at ask point B, with the software round as the example.

## D18. `play.lock` pins the script and roles; the log is JSON Lines (2026-10-23)

**Decision:**

- **The lockfile:** `roles.lock` becomes `play.lock`, because it now pins the script as well as the roles. Each remote reference is pinned to a commit and a content hash; a local folder only to a hash.
  - **Content hash:** the SHA-256 of a `sha256sum`-style listing of the package's files, sorted by path, excluding `.git/`.
  - **Checks:** the director refuses to start if a fetched package doesn't match its pin. `zanni play.yaml` checks that every remote package is pinned, whenever `play.lock` exists.
- **The log:** `log/<run-id>.jsonl`, append-only, one JSON object per line, with a fixed set of event types. Costs are decimal strings, or `null` when unknown (D7).
- **Checking a play against its script:** when the script is local, `zanni play.yaml` checks it against the script: every part is cast (unless optional), seats are within the script's limits, and gates are among the script's gates. A cast entry without `seats` takes its part's seats.
- **Seat cap:** `house_rules.max_seats_per_host` caps the seats the director casts onto one machine, because they share its GPU. The vision's first version runs several actors on one machine with a GPU.

**Why:**

- Pinning the script matters as much as pinning roles: a changed script changes the play.
- A content hash catches a tag that was moved.
- JSON Lines is append-only, readable with standard tools, and safe to write while a run is in progress.

**Not in the first version:** risk tiers.

## D19. Role packages: checking the whole folder, version tags, tiers as labels (2026-10-23)

**Decision:**

- **Folder checks:** `zanni <role folder>` checks the whole package:
  - `role.yaml`;
  - `AGENTS.md`, present and not empty;
  - every `skills/*/SKILL.md`, against the Agent Skills spec (agentskills.io/specification), with the name matching its folder;
  - `mcp.json`, in the standard `mcpServers` shape;
  - that every `needs.tools` name is an `mcp.json` server, and every `outputs` path is inside `needs.stage_write`.
- **Standard formats are checked, not tightened.** SKILL.md and `mcp.json` are standards shared with other tools, so their rules are enforced but fields Zanni doesn't define are left alone. D10's strictness applies to Zanni's own formats.
- **Secrets in `mcp.json`:** an `env` or `headers` value whose name looks like a secret must be a `${VAR}` reference. The value comes from the actor configuration or the environment (D15).
- **Versions:** `@X.Y.Z` resolves to the tag `path/to/role/vX.Y.Z` (for a role in a subfolder), then `vX.Y.Z`, then `X.Y.Z`. Two of them pointing to different commits is an error. Scripts resolve the same way.
- **Tiers:** `model.needs.tier` is a free label. The reference roles use `judgement`, `coding` and `basic`.
- **Not in the first version:** a role-level budget, and sandboxing roles from other people.

**Why:**

- **Tiers:** models change faster than a spec should, and the tier is only a hint (D11).
- **Version tags:** subfolder tags follow the convention of repositories that hold several packages.
- **Mismatched tags:** a version resolving two ways is refused, rather than guessed.

## D20. The actor configuration's models and credentials (2026-10-23)

**Decision:**

- **`models`:** an ordered list, with at least one entry.
  - **Provider:** each entry has a provider: `anthropic`, `openai`, `google`, `ollama`, or `openai-compatible` for any server with an OpenAI-compatible API, which needs a `base_url`.
  - **Optional fields:** `credential`, `tool_format` (`native` or `text`, D5), `price` (D7) and `fall_back_on`.
  - **Falling back:** the actor moves to the next model on the entry's reasons: `error`, `timeout`, `rate-limit`, `context` (the default four) and `refusal` (opt-in).
- **`credentials`:** a map of names to values, each stored or `${VAR}`. A model entry's `credential` names one. Every `${NAME}` in the role's `mcp.json` is looked up in `credentials` first, then in the environment.
- **Safeguards:** a configuration storing any value is refused if other users can read it or git tracks it. Values never appear in output or in error messages (D15).
- **Defaults:** `state_dir` defaults to `~/.zanni/actors/<name>`; `port` to `0`, meaning any free port.
- **Not in the first version:** the shared `models_list.yaml`. Each configuration holds its own list.

**Why:**

- **Lookup order:** one lookup rule for models and tools gives each actor its own credentials, without a shared `.env`.
- **`refusal` is opt-in:** a refusal is often the right answer, and shouldn't silently be retried elsewhere.
- **Provider names:** they are allowed here because the actor configuration is the one file that is about an instance. Roles, scripts and plays still never name a vendor (golden rule 4).

## D21. Casting on plain A2A 1.0: the director listens, the actor connects, a seat is a task (2026-10-24)

**Decision:**

- **The A2A version:** Zanni's director-to-actor protocol is A2A 1.0, the version `a2a-sdk` 1.2.3 implements (`PROTOCOL_VERSION_CURRENT = "1.0"`), over the JSON-RPC binding.
- **Who listens:** only the director. It serves its Agent Card at A2A's well-known path, with a `join` skill. The actor is always the A2A client and never listens, so it needs no open port and can run behind NAT.
- **A seat is one A2A task on the director, for the seat's whole life:**
  - **Join:** the actor sends a join message, which carries its own Agent Card inline. The director answers with a task.
  - **Cast:** the task moves to `working`, and its status message holds the cast.
  - **Refused:** the task moves to `rejected`, with the reason.
  - **Cue:** the director moves the task to `input-required`, and its status message holds the cue.
  - **Report:** the actor replies with a message on the same task.
  - **Release:** the director sends a release cue, the actor confirms, and the task moves to `completed`, or to `canceled` when the seat is recast.
  - **Heartbeats:** the actor follows the task with `SubscribeToTask` (streaming) or `GetTask` (polling), and each contact counts as one.
- **Zanni's own content:** every Zanni payload is a data part with a `kind` field, in a message that lists the casting extension's URI in `extensions`. Requests send the `A2A-Extensions` header.
- **Not used from A2A:** push notifications (the actor isn't reachable), `TASK_STATE_AUTH_REQUIRED`, and the extended agent card.

**Why:**

- Alessio's call at ask point A: the director listens and the actors connect.
- A multi-turn task is A2A's own way to have an agent ask for input. Here the director is the agent that coordinates, and each cue is its request for the actor's work.
- Keeping all of a seat in one task gives one id for the log, for credentials and for recasting.

**Supersedes:** `port` in the actor configuration (D20). An actor never listens, so it has no port.

**Deferred** (see `TODO.md`): how the director decides to accept an actor beyond checking its role and token, such as approving joins or allowlists.

## D22. The extension's URI lives in the repository until there is a domain (2026-10-24)

**Decision:** the casting extension's URI is `https://github.com/alessioricco/Zanni/blob/master/docs/spec/casting-extension.md#v1`.

- **Versioning:** the fragment is the version. Any change to a message's fields makes a new version (`#v2`), and an actor or director that speaks several versions lists one `AgentExtension` per version.
- **Strictness:** messages are validated strictly (D10), so a field from a newer version is an error to an older reader rather than silently ignored.

**Why:** Alessio's call. Zanni has no domain yet: `zanni.dev`, `zanni.org` and `zanni.ai` are registered, and `zanni.io` looked free on 2026-10-24. A URI in the repository Zanni controls works today, and opens the spec page.

**Revisit when:** a domain is registered. Moving the URI is itself a version change.

## D23. Every number on the wire is a decimal string (2026-10-24)

**Decision:** in casting messages and in the card extension:

- **Counts:** decimal strings, such as `"4"`.
- **Durations:** whole seconds, as decimal strings.
- **Money:** `{ "amount": "20.10", "currency": "USD" }`.
- **Ranges:** `{ "min": "1", "max": "4" }`.
- **Timestamps:** RFC 3339 UTC strings.
- **Checking:** each is checked against the published JSON Schema when it arrives.

**Why:** a round-trip through `a2a-sdk` 1.2.3's types showed that every number in extension params and data parts arrives as a protobuf float:

- `4` became `4.0`, and the range `{1, 4}` became `{1.0, 4.0}`;
- `9007199254740993` became `9007199254740992`;
- `20.10` lost its trailing zero.

Strings arrived exactly in every case. Approved by Alessio at ask point B.

## D24. Bearer tokens for joining and for seats; mTLS later (2026-10-24)

**Decision:**

- **Joining:** an actor joins with the play's join token, sent as an HTTP bearer token. The director reads it from `ZANNI_JOIN_TOKEN` in its environment; the actor holds it in its configuration's `credentials` as `ZANNI_JOIN_TOKEN` (D15).
- **At casting:** the director gives the seat two bearer tokens: `seat_token`, for every later call on the seat's task, and the stage's `token`, for its MCP server (D16). Both are scoped to that seat, carry an expiry (`expires_at`), and are revoked at release.
- **Not logged:** seat tokens appear only in the cast message, and are never logged (D15, D18).
- **Refusals:** a refusal names one reason from a fixed list (`not-authorised`, `bad-card`, `unsupported-version`, `no-such-part`, `part-full`, `host-cap`, `role-mismatch`, `hash-mismatch`, `needs-beyond-part`), with a plain-words message.
- **A new log event:** `join-refused`, because a refused join is the one casting event the log of D18 couldn't record. Its fields are `reason`, `actor` and `role`.

**Why:** Alessio's call at ask point C: make it work now, then make it better. Bearer tokens need nothing beyond what A2A's security schemes already declare.

**Deferred** (`TODO.md`): mTLS, per-actor join tokens, how the director accepts actors beyond its checks, and whether the director's join tokens come from a director configuration.

## D25. Protocol schemas generated from models; `jsonschema` for tests only (2026-10-24)

**Decision:**

- **Schemas:** the casting messages and card params are Pydantic models in `src/zanni/protocol/`, which never imports `a2a-sdk`. Their JSON Schemas (Draft 2020-12) are generated into `docs/spec/schemas/` with `uv run python -m zanni.protocol.schemas`, and a test fails if they drift.
- **Conformance:** checks examples against those schemas with `jsonschema`, a dev-only dependency.
- **Round-trip:** a separate test round-trips every valid example through `a2a-sdk`.
- **The whole stage:** the stage spec gains the rule `/` for "the whole stage", which direct git access needs (D16).

**Why:**

- One source for the code and the published schemas.
- Conformance that another implementation can run, with nothing but the schemas and a JSON Schema validator.
- `jsonschema` stays out of Zanni's runtime dependencies, because only tests need it.

## D26. Rehearsals: one actor, no director, cues from a file (2026-10-24)

**Decision:**

- **The file:** a rehearsal (recognised by `cues`) names a stage folder, a list of cues, and optional `verify` commands.
- **Running it:** an actor configuration runs it by pointing its `play` at it: `zanni <actor configuration>` then runs the cues locally, with no director.
  - **The stage:** it is copied fresh into the actor's `state_dir` for every run, and the actor's seat permissions are its role's needs.
  - **Reports and checks:** each cue's result is a `zanni.report`, the `verify` commands run in the stage copy, and every event goes to a JSON Lines log in the play log's format (D18).
- **In role packages:** a role package may ship rehearsals in `rehearsals/`, as its own tests, and `zanni <role folder>` checks them.

**Why:** Alessio's call at ask point A of milestone 2. Rehearsals are part of role packages, and let a role run with no director.

- **No configuration named:** a rehearsal can't name an actor configuration, because configurations are private to each machine. Pointing the configuration's `play` at the rehearsal keeps "one command, one file" (D9).
- **Reused by the director:** the same runner will drive actors when the director exists (milestone 4).

**Not in the first version:** sandboxing `verify` commands (and roles' MCP servers) for roles from other people (`TODO.md`).

## D27. Zanni's own fallback loop; Google as an optional extra (2026-10-24)

**Decision:**

- **The loop:** an actor runs a cue on its first model. On a failure, Zanni classifies it into D20's reasons, using Pydantic AI's exception types:
  - `rate-limit`: rate-limit and quota errors;
  - `context`: the request didn't fit the model's context window;
  - `timeout`: timeouts;
  - `refusal`: the content filter;
  - `error`: any other model API, connection or HTTP error.

  Zanni moves to the next model only if the failing entry lists that reason, and records every attempt.
- **Restarting:** a fallback restarts the cue on the next model. Work already written stays on the stage, and the next model sees it.
- **Ollama capabilities:** for Ollama entries, when the role needs tools and the entry uses native tool calling, Zanni asks the server (`/api/show`) before running, and refuses a model with no `tools` capability, suggesting `tool_format: text`. If the server can't be asked, the run's own fallback handles it.
- **Google models:** they need the optional `google` extra (`uv sync --extra google`). Without it, a `google` entry is refused in plain words.

**Why not Pydantic AI's `FallbackModel`:**

- it falls back on one set of exception types for the whole chain, while D20 gives each entry its own reasons;
- it doesn't tell Zanni which model answered and why the others were skipped, which the log needs.

The loop is about 25 lines.

**Why the extra:** `google-genai` is a large dependency most installs don't need. The pin stays exact (D8).

## D28. Running a rehearsal from the command line; the log's `fallback` event (2026-10-24)

**Decision:**

- **Running:** `zanni <actor configuration>` runs the rehearsal its `play` points at.
  - **Exit codes:** 0 when every cue is done and every `verify` check passed; 1 when the rehearsal ran but failed; 2 when the files have problems or nothing could start (a missing credential, a model that can't call tools).
- **`--check`:** validates any file without running anything, for CI and for looking before running.
- **The `fallback` event:** the run log gains `fallback` (`seat`, `model`, `reason`, `detail`). D18 had no place to record which model was skipped and why, and D27 requires it.

**Why:**

- **Exit codes:** CI and scripts need to tell "the role did poorly" (1) from "the files are wrong" (2).
- **`--check`:** "flags only override" holds: `--check` only narrows what the file would do.

## D29. The director's casting side is real code; a rehearsal is served by it (2026-10-24)

**Decision:**

- **Where:** the director's casting side lives in `src/zanni/director/`, and milestone 4 extends it rather than replacing it:
  - its card;
  - join checks (`src/zanni/protocol/fit.py`);
  - seats and their tokens;
  - cues and reports;
  - heartbeats and release;
  - the stage's MCP server.
- **Cues come from a rehearsal**, until milestone 4 gives the director a script to read.
- **`zanni <rehearsal> --serve`** serves a rehearsal as a play with one part, on the network:
  - **The part:** named after the role package that holds the rehearsal (the folder above `rehearsals/`). Its ceilings are that role's needs, and it has one seat.
  - **The checks:** an actor fits if its card names a role of that name (`role-mismatch` otherwise), and its role's content hash matches the package's (`hash-mismatch` otherwise). A rehearsal has no cast entry, so the check is by name and hash instead of by reference: a local reference differs from machine to machine, but the hash doesn't.
  - **The join token:** from `ZANNI_JOIN_TOKEN` in the director's environment, required.
  - **The address:** `--listen host:port` sets it, and defaults to `127.0.0.1` on a free port. The address is printed.
  - **The run:** the director serves one seat, runs the `verify` commands once the seat is released, and exits with D28's codes.
- **A local rehearsal runs over A2A too.** When an actor configuration's `play` is a local rehearsal, `zanni <actor configuration>` starts this director in the same process, on `127.0.0.1`, with a join token it makes up for the run. The actor joins it over A2A. So every rehearsal exercises the real wire, and the rehearsal's output and exit codes stay as D28.

**Why:** Alessio's call at ask point A of milestone 3. A fake director would test the actor against Zanni's own assumptions; a real one is half of milestone 4 already written, and lets one actor on another machine join for real.

**Supersedes:** "with no director" in D26. A rehearsal still needs no play file or script; it now runs with a director started for it.

## D30. What an actor configuration's `play` may point at (2026-10-24)

**Decision:** `play` is one of:

| Value | Recognised by | What the actor does |
|---|---|---|
| A director | an `http://` or `https://` URL not ending in `.yaml` or `.yml` | Fetches the director's card from `/.well-known/agent-card.json` under that URL. |
| A play file | a local path to a play file, or an `http(s)` URL ending in `.yaml` or `.yml` | Reads the play's `director` and joins it. A play file with no `director` can't be joined yet: starting local seats is milestone 4. |
| A rehearsal | a local path to a rehearsal | Runs it with a director started for it (D29). |

- **Before joining:** the actor prints the director's play and script, from its card. It refuses to join a director whose card doesn't carry the casting extension at a version it speaks, saying so in plain words. Nothing is sent to that director.
- **Exit codes:**
  - 0 when the seat is released with `done`;
  - 1 when it's released for any other reason;
  - 2 when the join is refused or nothing could start.

- **Director addresses are `http(s)`:** A2A's JSON-RPC binding (D21) runs over HTTP, so a play's `director` is an `http` or `https` URL. The `ws` and `wss` addresses the play file used to allow are gone.

**Why:** Alessio's call at ask point B. A director's URL is all a remote actor needs. A play file is what a user already has, and a rehearsal keeps D26.

## D31. The folder stage is served over MCP from milestone 3 (2026-10-24)

**Decision:**

- **The server:** the director serves the `folder` stage as an MCP server, over Streamable HTTP. The address goes in the cast's `stage.mcp_url`; Zanni's director uses `/stage/mcp` under its own address.
- **Tokens:** each call carries the seat's stage token as an HTTP bearer token. A missing, unknown, expired or revoked token gets HTTP 401.
- **The tools:** `stage_read`, `stage_write`, `stage_list`, `stage_delete` and `stage_changes`, with the arguments and results of `docs/spec/stage.md`.
  - **Errors:** a refused operation is a tool result with `isError`, whose text ends with `<code>: <message>`, such as `not-permitted: this seat may not write app/x.py; …`. It only has to end with it, because the `mcp` SDK puts `Error executing tool <name>: ` before every tool error's text.
- **The actor's side:** Zanni's actor reaches the stage through the official `mcp` client. It turns those errors back into the stage errors its local tools raise, so a model sees the same tools and the same errors on a local and a remote stage.
- **Calls on a seat's A2A task:** a call with a missing, wrong, expired or revoked seat token fails with a JSON-RPC Invalid Request error (`-32600`) whose message starts with `not-authorised`. A2A defines no error for this.
- **An open stream counts as contact:** an open `SubscribeToTask` stream counts as contact for as long as it stays open.
- **Milestone 5:** the git backend, and direct git access (D16), stay there.

**Why:** Alessio's call at ask point C. `zanni.cast` already requires `stage.mcp_url`, and without it an actor on another machine has no stage.

## D32. Each actor keeps its own log; machines are described by role, not hardware (2026-10-24)

**Decision:**

- **The actor's log:** every actor keeps its own log on its own machine, in JSON Lines (D18), at `<state_dir>/plays/<play>/<run-id>/log.jsonl`, one folder per run, since a refused join has no seat. For a rehearsal, it goes next to the director's log in the run folder, as `actor-log.jsonl`. It records:
  - `joined`: the director's URL, play and script, the seat, part, permissions and expiry, never a token;
  - `join-refused`, `cue`, `fallback`, `report` and `cost`;
  - `released`.

  The director keeps the play's log. Neither depends on the other.
- **Where an actor runs is up to whoever runs it.** A director never assumes its actors' machines. In time, a director may hire actors that other people offer online.
- **The project describes machines by their role:**
  - in docs, decisions, examples and recorded runs, a machine is named for what it does, such as "director and actor on one machine", "the actor on a second machine on the same network" or "a local model server";
  - recorded runs still name exact models and versions (golden rule 7);
  - the maintainer's own machines are kept out of the repository.

**Why:** Alessio's answer at ask point D of milestone 3: each actor must be able to log its own work locally, and one contributor's setup is a detail that shouldn't shape the project for everyone else.

## D33. The director is an agent acting through tools that code checks (2026-10-24)

**Decision:** `zanni play.yaml` runs the director as an agent loop on its own models (D34). Its instructions are Zanni's built-in director role, the script's prose and frontmatter, the cast and the house rules. It can read the stage, and it acts only through tools, each of which checks the rules in code before acting and refuses in plain words when they forbid it:

- `cue(seat or part, scene, instructions, reads, writes, deadline, budget)` and `wait_for_reports()`;
- `run_verifier(name)` and `ask_gate(name, summary)`;
- `cast(part, seats)` and `release(seat, reason)`;
- `end_round()` and `stop(reason)`.

- **State in code:** rounds, spend, seats, pending cues, reports, verdicts and gate decisions are kept by the director's code, not in the model's context. Each turn is a fresh model run, given a summary of that state and the reports that arrived since the last turn, marked as actors' reports (data, never instructions).
- **Three rules in code,** because a director often runs unattended:
  1. **"Done" is checked.** `stop("done")` is refused unless every gate in the script's frontmatter that the play enforces was approved, and every verifier in the script's `stop.done_when` passed after the stage's last change (D35). A script without `done_when` falls back to every verifier run in the last round passing, at least one of them, and the log warns that "done" was weakly checked. Any other reason (`budget`, `stuck`, …) ends the run as not completed.
  2. **The director falls back, then pauses.** Its models are an ordered list with fallback, like an actor's (D27). When every model fails, the play pauses: the director logs `paused`, sends no new cues and keeps every seat's heartbeat. The owner resumes it with `zanni gate … resume` (D38). `gate_timeout` applies to a pause too, stopping the run with reason `paused`. The play's state lives in the director's process: surviving a restart of that process is deferred (`TODO.md`).
  3. **A turn cap per round.** The house rule `max_director_turns` (default 30) limits the director's model turns in one round. When it is reached, the round ends; if the round's work isn't verified, the run stops with reason `director-turns`.
- **Stop reasons:** `done`, `budget`, `gate`, `paused`, `director-turns`, `max-rounds`, or the director's own reason.

**Why:** Alessio's call at ask point A of milestone 4. A script is prose for an agent (D17), so an agent must read it; but every hard rule stays in code (golden rule 5).

**Considered and set aside:**

- **Code-driven:** parse acts and scenes from the headings and run them with no model. Every script would need one shape, which D17 rejected; the two example scripts already read differently.
- **Hybrid:** code walks the headings, the model writes the cues. It still needs a model, still breaks on prose that isn't neatly headed, and rules 1 and 3 give most of its predictability.

## D34. The director's configuration is an actor configuration with role `zanni:director` (2026-10-24)

**Decision:**

- **The file:** a director configuration is an actor configuration whose `role` is `zanni:director`, Zanni's built-in director role, shipped in the package, and whose `play` is a local play file. It has the director's models, in order with fallback, and its credentials, under D15's safeguards.
- **Where it is found:** `zanni play.yaml` uses `--director <file>`, then `director.yaml` beside the play file. Nowhere else: when there is none, the error names both places.
- **Either file starts the play:** `zanni director.yaml` runs its `play`, as `zanni play.yaml` does. A director configuration whose `play` names another play is refused.
- **Tokens:** `ZANNI_JOIN_TOKEN` and `ZANNI_OWNER_TOKEN` (D38) come from its `credentials`, one of each per play. They may be `${VAR}` references, so a director configuration with only references may be committed.
- **Only `zanni:director` can direct.** A configuration is a director's exactly when its role is `zanni:director`. Any other `zanni:` name is refused, and `--director` given a configuration with another role is refused too.

**Why:** Alessio's call at ask point B. The director is an actor too, so it reuses the format, the safeguards and the fallback. This answers "The director's own configuration" in `TODO.md`.

**Considered and set aside:**

- **`~/.zanni/director.yaml` as a fallback:** join and owner tokens belong to one play; a global file would share them across plays, and pick models silently. A global defaults file is deferred (`TODO.md`).
- **Models from the environment only** (`ZANNI_DIRECTOR_MODEL`): one model, no fallback.
- **`zanni play.yaml` only validating:** against "one command, one file".

**Deferred** (`TODO.md`): custom director roles with their own instructions.

## D35. Verifiers are named in the script's frontmatter; the play gives project-specific commands (2026-10-24)

**Decision:**

- **In the script:** `verifiers:` maps a name to `{ description, command, timeout }`. `description` says what it checks; `command` is an optional default; `timeout` defaults to 300 seconds. The prose refers to verifiers by name, and the director's `run_verifier` accepts only these names.
- **In the play:** `verifiers:` maps a script verifier's name to its own `{ command, timeout }`. A play can't add or remove names. A verifier with no command, after the play's, is refused by `zanni --check` before anything runs.
- **Running one:** the director runs the command in the stage folder, with the user's permissions (as rehearsals do, D26), and logs a `verdict`. Only verdicts mark work done.
- **"Done" names its verifiers:** `stop.done_when` lists the verifiers that must pass, each after the stage's last change, for `stop("done")` (D33). A later write makes an earlier pass stale. Not every verifier must pass at the end: "every new test fails" is meant to fail by then.
- **No verdict while work is in flight:** `run_verifier` is refused while a cue that writes to the stage is pending.
- **Commands from someone else's script:** `zanni --check` and the director's start-up output list every command that will run, and whether it came from the script or the play. The commands come from the script version pinned in `play.lock` (D37), so they can't change between runs unless the lock does.

**Why:** Alessio's call at ask point C. The script knows what must be checked; only the play knows the project's commands (`pytest`, `npm test`).

**Considered and set aside:** verifiers as MCP servers the script names (heavier, and a command covers it); verifiers as parts played by actors (a verdict must not be an actor's opinion).

**Deferred** (`TODO.md`): soft verifiers (a model judging), verifiers run on one workstream instead of the whole stage, and sandboxing verifier commands.

## D36. Local seats are actor subprocesses the director starts (2026-10-24)

**Decision:**

- **The list:** a director configuration's `seats:` maps a part to actor configuration files, one file per seat. The director starts each as `zanni <configuration> --play <director URL>`, gives it the join token in its environment, and stops it at the end. Each actor uses its own configuration's models and credentials, and keeps its own log (D32).
- **`--play`:** a new flag that overrides an actor configuration's `play`. A flag overrides only what a file can say (D9).
- **`host: local` is a requirement:** a part with `host: local` and no local seats listed is refused. A part without it may have local seats, and actors may also join it. The director can't start more local seats than files listed.
- **What the director reads:** only `name` and `role` from each file. The role must be the one the play casts for that part (the same remote reference, or the same local folder), and names must be unique. The director never resolves those files' credentials.
- **No orphans:** each subprocess watches a pipe from the director (its standard input) and exits as soon as it closes, even mid-cue. The heartbeat timeout stays as the backstop.
- **Crashes:** a local seat that dies is restarted up to twice per play, and its pending cue is resent. After that, its seat is left to an actor joining, or the stop rules end the run.
- **Local roles at casting:** a local cast reference differs from machine to machine (D29), so for a local cast entry an actor fits if its role has the name and content hash of the folder the play names. A remote cast entry still needs the same reference, and the hash pinned in `play.lock`.
- **The join token:** an actor reads `ZANNI_JOIN_TOKEN` from its configuration's `credentials`, or else from its environment.

**Why:** Alessio's call at ask point D. The director never holds an actor's keys, and one command runs a whole play on one machine.

**Considered and set aside:** running local seats in the director's own process (it would hold their keys); no local seats in this milestone.

**Deferred** (`TODO.md`): several seats from one file.

## D37. Fetching packages with git; `play.lock` written once, updated only on request (2026-10-24)

**Decision:**

- **Resolving:** `host/owner/repo[/path]@version` is the git tag `v<version>` or `<version>` on `https://<host>/<owner>/<repo>.git`, fetched with the `git` command. `version` must be `major.minor.patch`; a missing tag is refused, listing the nearest tags.
- **The cache:** `~/.zanni/packages/<host>/<owner>/<repo>/<commit>/`. A package in a subfolder uses that folder, and its hash covers that folder only.
- **The lockfile:** the director writes `play.lock` the first time it resolves the play's packages. After that:
  - a pinned commit already in the cache is used without touching the network, after its hash is checked;
  - a tag that now points to another commit is refused, naming both commits;
  - only `zanni play.yaml --update` re-resolves the tags and rewrites `play.lock`, printing the changed commits and the verifier commands that changed.
- **Local packages:** pinned by hash only. A local package that changed since `play.lock` is reported, not refused, and the director uses its current hash; `--update` re-pins it.
- **Authentication is git's:** Zanni passes no credentials. Private repositories use the person's own SSH keys or credential helper, and `url.<base>.insteadOf` in their git config. Git runs with `GIT_TERMINAL_PROMPT=0`, so an unattended fetch fails instead of waiting for a password.
- **Fetching runs nothing:** one tag, shallow, no submodules; git never copies a repository's hooks.
- **Actors** fetch remote roles the same way.

**Why:** Alessio's call at ask point E. A director running unattended must not depend on the network once its packages are fetched, nor change what it runs without being asked.

**Considered and set aside:** local folders only until milestone 5; each host's archive API (code per host, and it bypasses git's authentication).

**Deferred** (`TODO.md`): version ranges, cleaning the cache, and checking signed tags.

## D38. Gates pause the play; the owner decides from anywhere (2026-10-24)

**Decision:**

- **A gate is a state of the play.** At a gate the play enforces (`house_rules.gates`), the director logs `gate-pending` with a summary (the scene, the files changed since the last gate, the verdicts), sends no new cues, and keeps every seat's heartbeat. A gate the play doesn't list is skipped, and logged as skipped.
- **Deciding:** `zanni gate <play file or director URL> [approve | reject | resume] [--note …]` shows or decides a pending gate, or resumes a paused play (D33). With a play file, it finds the running director through `log/director.json`, which the director writes beside its log while it runs (its URL and run id, never a token), or else the play's `director`.
- **The owner token:** `ZANNI_OWNER_TOKEN`, one per play, separate from the join token, so no actor can decide a gate. The director's comes from its configuration (D34); `zanni gate` reads it from its own environment, never a flag. It is never printed or logged.
- **How `zanni gate` reaches the director:** a small HTTP endpoint beside A2A, at `/zanni/owner` under the director's address: `GET` returns the play's state and any pending gate or pause, `POST` decides. A missing or wrong token gets HTTP 401.
- **A deadline:** `house_rules.gate_timeout` (whole seconds, or a number with `s`, `m` or `h`) stops the run with reason `gate` when it passes. With none, the play waits.
- **A convenience:** when the director runs in an interactive terminal, it also offers the same choice there.

**Why:** Alessio's call at ask point F. A director often runs in the background, on a machine nobody is sitting at.

**Why an HTTP endpoint and not A2A:** in A2A, the director's tasks are seats, and every call on them is an actor's. An owner isn't an agent, and a gate decision isn't a conversation: two plain JSON calls say it, and keep owner calls out of the seats' tasks entirely.

**Considered and set aside:** approval on the director's terminal only (a background director would stop at its first gate forever); approval by a file in the play folder (it only works on the director's machine).

**Deferred** (`TODO.md`): telling someone a gate is waiting, per-person approvers, and a web page for gates.

## D39. Budgets are reserved per cue and enforced by actors; unpriced actors are refused at join (2026-10-24)

**Decision:**

- **What counts:** the play's spend is every report's `cost` plus the director's own.
- **Priced at join:** `zanni.join` carries `pricing: known` when every model the actor may use has a price (published, or `price:` in its configuration). Under a budget, an actor with `unknown` pricing is refused with a new reason, `unpriced`. The director's own models must be priced too, or the play doesn't start.
- **A budget per cue:** `zanni.cue` carries `limits.budget`. By default it is the budget not yet reserved, divided among the seats with no pending cue; the director's model may give less, never more. A pending cue reserves its budget; its report replaces the reservation with the actual cost. When nothing is left to reserve, the run stops with reason `budget`.
- **The actor stops at it:** after each model response, the actor's engine checks the cue's spend; at the limit, it ends the cue and reports `outcome: over-budget`, with the cost so far. Overshoot is bounded by one model call.
- **Unknown cost that gets through:** under a budget, the seat is released with reason `budget` and its part recast, and the spend is shown as "at least" from then on. With no budget, unknown cost is logged and the play goes on.
- **The director's own turns:** before each turn, the director stops with reason `budget` if the spend has reached it.
- **A written limit:** the budget counts what actors report. A modified actor could under-report; the real cap on a key is its owner's.
- **A new extension version:** these change `zanni.join`, `zanni.refused`, `zanni.cue` and `zanni.report`, and the casting extension says any change to a message makes a new version, so its URI moves from `#v1` to `#v2`.

**Why:** Alessio's call at ask point G. D7 says unknown cost is never zero, and must be caught before a seat is cast, not after it has spent.

**Considered and set aside:** stopping the whole play at the first unknown cost (the check at join prevents that case); allowing unknown cost when the house rules opt in (contradicts D7).

**Deferred** (`TODO.md`): an actor's own spending cap in its configuration; token budgets.

## D40. The slug kata: the example play for milestone 4's recorded runs (2026-10-24)

**Decision:** `examples/scripts/slug-kata/` and `examples/plays/slug-kata/`. A tester (`slug-tester`) writes failing tests; up to two coders (a new `slug-coder` role) make them pass. Round 1 has two independent items in separate files, so two coders work in parallel; round 2 extends one of them. Two verifiers: `tests-fail` before the `plan` gate, and `tests-pass`, the script's `done_when`. The play folder ships `director.yaml` and the local seats' configurations, with `${VAR}` credentials only and priced models. It is run from a copy, because the stage is the play's own folder.

**Why:** Alessio's call at ask point H. It is small enough for a local model, needs no network, and exercises two parts, a range of seats, a gate, two verifiers, rounds and the budget.

**Considered and set aside:** the newsroom script (web fetching, three new roles); a reduced software script now (milestone 6's work, done twice).

## D41. A report's changes come from the stage's record, not the actor (2026-10-24)

**Decision:** the folder stage records which seat made each change. When a report arrives, the director logs the changes that seat made while its cue was pending, from that record, and ignores the actor's own list.

**Why:** with several seats writing at once, an actor can't tell its own changes from another seat's (`TODO.md`, "A report's change markers with several seats"). The stage knows, and it can't be bypassed (golden rule 5).
