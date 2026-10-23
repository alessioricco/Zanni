# Decisions

Each decision says what was decided, why, and what would make us revisit it. Newest last. A decision is changed by adding a new one that supersedes it, not by editing the old one.

## D0. Foundations (2026-10-22)

- **Python 3.12+ and uv**, with one entry point: `zanni <file>.yaml`. Rust was considered and set aside for now.
- **MIT licence.**
- **Name:** "Zanni", held on PyPI (0.0.1 placeholder) and at `github.com/alessioricco/zanni`.
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
