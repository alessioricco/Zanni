<!-- Copied from the throwaway spike repo (zanni-spike, local only, not published). File paths below refer to that repo. -->

# Zanni spike: Pydantic AI as the actor engine

Run on 2026-10-23, in one Claude Code session. Every result below ran in that session; nothing is projected.

**Recommendation: go**, behind the engine adapter, with the gaps below planned as Zanni code.

## Versions

| Component | Version |
|---|---|
| Python | 3.14.4 (uv 0.10.4) |
| pydantic-ai-slim | 2.60.0 (extras: anthropic, mcp, openai) |
| mcp (official SDK) | 2.3.0 |
| fastmcp-slim (Pydantic AI's MCP client) | 4.1.3 |
| a2a-sdk (official) | 1.2.3 |
| genai-prices | 0.1.13 |
| Ollama server | 0.40.6, on a separate machine on the same network |
| Local model | `qwen3.8:27b` (digest aaee06c39dcf, 27.3B, Q4_K_M) |
| Model without tool calling | `gemma3:4b` (digest 68ceab7e468a, 3.9B, Q4_K_M, 3.35 GB), pulled for item 4 |
| Cloud model | `claude-haiku-5-5` (Anthropic API) |

The task for every full run was: "Read stage/spec.md and write one pytest test for its first acceptance criterion into stage/tests/". Each run got a fresh copy of the stage, which has a two-line spec and a small `app/slug.py` to test against. A run succeeded when pytest collected at least one test in `tests/` and it passed.

## Results per item

Line counts are non-blank, non-comment lines, docstrings included.

| # | Item | Worked | Pydantic AI provided | Zanni wrote | Lines |
|---|---|---|---|---|---|
| 1 | Role loading | Yes. AGENTS.md as instructions; skills **on demand**: the instructions list each skill's name and description, and a `load_skill` tool returns the body. Both models loaded the skill unprompted in the full runs. | `instructions=`, `FunctionToolset`, `ModelRetry` | AGENTS.md and SKILL.md parsing, on-demand skill tool | 45 (`spike/role.py`) |
| 2 | Model switching | Yes. Same actor on `qwen3.8:27b` and `claude-haiku-5-5`; **no code changed**, only the `models.yaml` entry name. | Ollama provider (OpenAI-compatible), Anthropic model | `models.yaml` loader; appends `/v1` to `OLLAMA_BASE_URL`, which the provider doesn't do | 24 (`spike/models.py`) |
| 3 | Scoped tools | Yes. `read_file`/`write_file` check the role's `stage_read`/`stage_write` in the tool. 7 unit tests pass (`..`, absolute paths, symlink escape, writing to `spec.md` or `app/`). Live: Haiku called `write_file('../escaped.txt')` and got "Refused: … outside the stage"; nothing was written. | `FunctionToolset`; `ModelRetry` returns the refusal to the model | The scope check | 32 (`spike/stage_tools.py`) |
| 4 | No native tool calling | Yes, with a prototype. No built-in fallback (see below). | `WrapperModel` to hook requests | Opt-in text tool format | 64 (`spike/text_tools.py`) |
| 5 | MCP | Yes. Stub server over stdio with `verify(path)` running pytest. Both models wrote the test, then called `verifier_verify` and got "pass: 1 passed". | `load_mcp_toolsets()` reads the role's `mcp.json` (standard `mcpServers` format, `${VAR}` expansion, tool names prefixed by server) | The stub server, on the official `mcp` SDK (`MCPServer`; FastMCP was renamed in mcp 2) | 19 (`spike/verify_server.py`), 0 for the client |
| 6 | A2A | Yes. The actor serves A2A (JSON-RPC) with an Agent Card built from `role.yaml`; the director fetched the card, sent the task and got `TASK_STATE_COMPLETED`, a report and a `pass` verdict, on both models. | Nothing; Pydantic AI 2.60 has no A2A support of its own | Agent executor, card builder, role extension, director | 58 (`spike/a2a_actor.py`) + 31 (`director.py`) |
| 7 | Cost per run | Yes. Haiku is priced natively; local is priced from a host-declared price; unpriced stays "unknown". | `RunUsage.cost` via genai-prices; `UsageLimits(cost_limit=…)` | Fallback to host-declared price per Mtok; "unknown", never zero | 19 (`spike/cost.py`) |
| 8 | Measure | Yes, below. | `RunUsage` (tokens, requests) | Runner, footprint probe | 57 (`spike/measure.py`), 26 (`spike/actor.py`) |

Supporting code: `spike/ledger.py` (17 lines) records every run's cost and enforces the $1.00 cap.

### Item 6 details

- **The Agent Card can carry Zanni's role fields.** The role's `needs`, `never` and `model.needs` went into `AgentCapabilities.extensions` (uri `https://zanni.dev/a2a/ext/role/v0`) and round-tripped intact through the director, nested lists and dicts included. One caveat: `params` is a protobuf `Struct`, which has no integer type, so numbers arrive as floats. Budgets and seat counts would need to be strings or have their type checked on arrival.
- **The client's default HTTP timeout is 5 s.** The first director call on the local model timed out with `A2AClientTimeoutError`, because a run takes about 10 s. Passing an httpx client with a longer timeout through `ClientConfig(httpx_client=…)` fixed it. Real cues should use the A2A task with polling or streaming instead of one long blocking call.
- **FastA2A.** `github.com/pydantic/fasta2a` now redirects to `github.com/datalayer/fasta2a`; the latest release is 2.1.1 (2026-10-05). It is its own A2A implementation (it doesn't depend on `a2a-sdk`), with an optional `pydantic-ai` extra. I didn't build with it. It would probably save the roughly 25 lines of executor boilerplate, but it would put a third-party A2A implementation between Zanni and the spec. With the official SDK, Zanni keeps control of the card and the casting extension, which are part of the spec. Recommendation: stay on `a2a-sdk`.

### Item 7 details

- Price source: genai-prices 0.1.13, the snapshot bundled with Pydantic AI. It lists `claude-haiku-5-5` at $0.50 input / $2.50 output per million tokens.
- **An unpriced model gets no cost, and no warning.** genai-prices has no `ollama` provider, so `usage.cost` is `None`, and Pydantic AI says nothing unless a `cost_limit` is set.
- **`cost_limit` is enforced, but after the fact.** With `cost_limit=0.0001`, the Haiku run raised `UsageLimitExceeded` at $0.0001347. The limit is checked after each response, so the request that crosses it has already been paid for.
- **`cost_limit` can't protect an unpriced model.** It only emits `CostNotFoundWarning`, and the run continues. The director must treat "unknown" cost as not safe for the budget: it should require a declared price or fall back to a token budget.

## Measurements (item 8)

All 9 runs are listed below. Each was one process making sequential runs against a fresh stage; times are wall clock from the laptop.

| Model | Run | Success | pytest | Time (s) | Requests | Tokens in / out | Cost (USD) | Tools called |
|---|---|---|---|---|---|---|---|---|
| qwen3.8:27b | 1 | ✅ | 1 passed | 7.2 | 3 | 2410 / 184 | 0 (declared) | read_file, load_skill, write_file |
| qwen3.8:27b | 2 | ✅ | 1 passed | 8.3 | 3 | 2421 / 224 | 0 (declared) | read_file, load_skill, write_file |
| qwen3.8:27b | 3 | ✅ | 1 passed | 12.9 | 3 | 2525 / 321 | 0 (declared) | read_file, load_skill, write_file |
| claude-haiku-5-5 | 1 | ✅ | 1 passed | 8.8 | 3 | 3475 / 260 | 0.0004775 | read_file, load_skill, write_file |
| claude-haiku-5-5 | 2 | ✅ | 1 passed | 3.0 | 3 | 3475 / 278 | 0.0004865 | read_file, load_skill, write_file |
| claude-haiku-5-5 | 3 | ✅ | 1 passed | 3.2 | 3 | 3475 / 265 | 0.0004800 | load_skill, read_file, write_file |
| gemma3:4b + text tools | 1 | ❌ | 1 failed | 2.8 | 3 | 1671 / 135 | unknown | read_file, write_file |
| gemma3:4b + text tools | 2 | ❌ | 1 failed | 2.9 | 3 | 1671 / 153 | unknown | read_file, write_file |
| gemma3:4b + text tools | 3 | ❌ | 1 failed | 2.2 | 3 | 1671 / 110 | unknown | read_file, write_file |

Totals: `qwen3.8:27b` 3/3, `claude-haiku-5-5` 3/3, `gemma3:4b` with text tools 0/3. All three gemma failures had the same cause: the test called `app.slug.slugify(...)` without importing `app`, which raised `NameError`. The tool calls themselves worked every time. The model skipped the `write-test` skill, which would have told it how to import. This is one model and three runs, so it shows that the mechanism works, not how good small models are.

The A2A actor process, measured 3 times on the laptop:

| Measure | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Startup to Agent Card served (s) | 2.12 | 1.31 | 1.18 |
| Idle memory after 5 s (macOS `phys_footprint`) | 131 MB | 130 MB | 131 MB |

`ps` RSS reported about 18 MB for the same processes, because macOS compresses idle pages; `phys_footprint` includes them.

## Models without native tool calling

- **Pydantic AI 2.60 has no built-in fallback** for function tools. `PromptedOutput` covers only the final structured output, not tool calls.
- **Nothing warns you in advance.** Pydantic AI doesn't ask Ollama what a model can do: for `gemma3:4b` the profile says `supports_tools=True`. The run fails on the first request with `ModelHTTPError` 400: "registry.ollama.ai/library/gemma3:4b does not support tools".
- **A fallback fits without forking Pydantic AI.** I wrapped the model in a `WrapperModel` (64 lines):
  - the model is sent no tools; they are described in the prompt instead;
  - earlier tool calls and results are replayed as text;
  - ```` ```tool {"tool": …, "args": …} ```` blocks in the reply are parsed back into tool calls.
  
  The agent loop, the toolsets and the scope checks run unchanged.
- **It is opt-in per model entry** (`tool_format: text` in `models.yaml`), so cloud models are never affected.
- **What it doesn't cover yet:** streaming, structured output types (only `str` output was tested), a model that writes text and a tool block in the same reply, and repair of malformed blocks. A malformed block is currently left as text.
- **None of the other local models needed it.** All eight report `tools` in Ollama's `/api/show`; `gemma3:4b` was pulled only for this item.

## Gaps Zanni must fill on top of Pydantic AI, by effort (largest first)

1. **The A2A layer.** This means the executor, the card builder and the casting extension (join, seat, scoped credentials, release). Long cues also need tasks with polling or streaming. Pydantic AI contributes nothing here.
2. **A production text tool fallback.** It needs multiple calls per reply, malformed-block repair and streaming, and conformance tests on several small models. The prototype proves the hook point, not the robustness.
3. **Budgets in the director.** It must add up cost across seats, treat unknown costs as unsafe, and stop a seat before the request that would cross the limit rather than after. Pydantic AI's `cost_limit` is per run and checked after each response.
4. **Detecting what a local server supports.** For example, read Ollama's `/api/show` and set `supports_tools`, so a missing capability is caught before a run, with a clear message, rather than as an HTTP 400 mid-play.
5. **Role loading.** AGENTS.md plus skills on demand took 45 lines. A real version needs SKILL.md frontmatter validation and skill resources (files beside SKILL.md).
6. **Local prices.** Hosts declare a price per million tokens for local models, which can be 0, and genai-prices covers the cloud.

Not a Pydantic AI gap, but noted: in the spike, the scope check lives in the actor's own tools. Under the trust model, the stage enforces it (for example, git branch permissions), because the actor's host can't be trusted to.

## Go or no-go: go

Reasons:
- Switching models is configuration only: the same actor ran on a local Ollama model and on Anthropic with no code change.
- MCP needs no client code: the role's standard `mcp.json` loads directly.
- Cost per run and a cost limit are built in for priced models.
- Every gap above was filled from outside Pydantic AI (wrappers, toolsets, an adapter) without patching or forking it, which is what the engine adapter needs.
- Glue for items 1–7 came to about 290 lines.

Risks to manage:
- **Churn.** Pydantic AI is at 2.60 with a large, fast-moving API. A2A left the core package, and a promotional banner prints on every run unless `PYDANTIC_AI_NO_BANNER=1`. Pin versions, keep it behind the adapter, and run the conformance tests on every upgrade.
- **Two MCP implementations.** Pydantic AI's MCP client is FastMCP's, not the official `mcp` SDK's. The two interoperated over stdio here, but Zanni's conformance tests should cover a server built on the official SDK.

## Surprises

- The first escape probe exercised nothing: both models refused, on their own, to write outside the stage. Only an explicit "authorised sandbox test" got one model (Haiku) to call the tool, which then refused. Model refusals are not a control, which is why the check is in the tool.
- `qwen3.8:27b` was reliable here: 3/3, with the skill loaded every time, at 7–13 s per run against 3–9 s for Haiku.
- `OllamaProvider` doesn't add `/v1` to `OLLAMA_BASE_URL`, although Ollama's OpenAI-compatible API lives there.
- A Pydantic AI file named `_uuid.py` shadows the standard library when Python is started from inside the package folder. That only matters for tooling run from that folder.

## Spend

- Total cloud spend: **$0.0044** of the $1.00 cap. That is $0.0043049 from 9 Haiku runs recorded in `runs/spend.jsonl`, plus $0.0001347 from the run stopped by `cost_limit`, which raised before the ledger could record it.
- Local runs cost nothing per token.
