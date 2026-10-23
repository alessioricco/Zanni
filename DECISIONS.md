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
