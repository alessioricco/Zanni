# Milestone 2: recorded runs

Run on 2026-10-24 on two machines: one running `zanni`, and a local model server (Ollama) on a second machine on the same network. Every result below ran; nothing is projected. Claims about milestone 2 in the docs point here.

## What ran

The `smoke` rehearsal of the example role `slug-tester` (`examples/roles/slug-tester/`): one cue, "write one pytest test for each acceptance criterion", against a two-criterion backlog. The verifier is `pytest` on the stage copy afterwards: the run passes only if both tests exist and pass. Each run used a fresh copy of the stage.

Between runs, **only the actor configuration changed**: the model entry. The role, the rehearsal and the code were the same.

| Component | Version |
|---|---|
| zanni | `master` + the `engine-adapter` branch at `4709d44` (item 7), plus the text-format fixes described below |
| Python | 3.14.4 |
| pydantic-ai-slim | 2.60.0 |
| mcp | 2.3.0 |
| Ollama server | 0.40.6 |
| `qwen3.8:27b` | digest `aaee06c39dcf`, 27.3B, Q4_K_M, native tool calling |
| `gemma3:4b` | digest `68ceab7e468a`, 3.9B, Q4_K_M, no native tool calling (Ollama capabilities: completion, vision) |
| `claude-haiku-5-5` | Anthropic API |

## Results

### Set 1: before the text-format fixes

| Model | Tool format | Run | Verifier | Time (s) | Tool calls | Tokens in / out | Cost |
|---|---|---|---|---|---|---|---|
| qwen3.8:27b | native | 1 | ✅ 2 passed | 16.4 | 4 | 3361 / 345 | $0 (configured) |
| qwen3.8:27b | native | 2 | ✅ 2 passed | 16.4 | 4 | 3379 / 340 | $0 (configured) |
| qwen3.8:27b | native | 3 | ✅ 2 passed | 26.2 | 4 | 4743 / 542 | $0 (configured) |
| gemma3:4b | text | 1 | ❌ no tests ran | 16.5 | 3 | 6332 / 429 | $0 (configured) |
| gemma3:4b | text | 2 | ✅ 2 passed | 9.7 | 4 | 4869 / 339 | $0 (configured) |
| gemma3:4b | text | 3 | ✅ 2 passed | 9.0 | 4 | 4699 / 302 | $0 (configured) |
| claude-haiku-5-5 | native | 1 | ✅ 2 passed | 7.4 | 4 | 4926 / 429 | $0.0007071 |
| claude-haiku-5-5 | native | 2 | ✅ 2 passed | 7.4 | 4 | 4926 / 426 | $0.0007056 |
| claude-haiku-5-5 | native | 3 | ✅ 2 passed | 7.0 | 4 | 4926 / 471 | $0.0007281 |

Times are wall clock for the whole `zanni` command, including start-up and the verifier. Costs come from published prices for Haiku (genai-prices, through Pydantic AI). For the local models they come from the `price: { input: 0, output: 0 }` set in the configuration (D7).

### Set 2: `gemma3:4b` after closing unbalanced braces

| Model | Tool format | Run | Verifier | Time (s) | Tool calls | Tokens in / out | Cost |
|---|---|---|---|---|---|---|---|
| gemma3:4b | text | 1 | ✅ 2 passed | 10.4 | 5 | 6143 / 373 | $0 (configured) |
| gemma3:4b | text | 2 | ✅ 2 passed | 8.3 | 4 | 4869 / 277 | $0 (configured) |
| gemma3:4b | text | 3 | ❌ no tests ran | 280.6 | 3 | 3663 / 15503 | $0 (configured) |

### Totals

| Model | Passed |
|---|---|
| qwen3.8:27b (native) | 3 / 3 |
| claude-haiku-5-5 (native) | 3 / 3 |
| gemma3:4b (text format), set 1 | 2 / 3 |
| gemma3:4b (text format), set 2 | 2 / 3 |

These are three runs per model on one small task: they show the mechanisms work, not how good these models are.

### Falling back

The configuration listed two entries: `qwen3.8:27b` at an unreachable address (`http://127.0.0.1:9`), then `qwen3.8:27b` on the model server. The first failed with a connection error, classified as `error`. The actor moved to the second, which passed (✅ 2 passed, 25.2 s, including the failed attempt). The log recorded a `fallback` event naming the model and the reason.

### Refusing a model that can't call tools

`gemma3:4b` with `tool_format: native` was refused before anything ran, in 2.7 s, exit code 2:

```
gemma-native.yaml: ollama gemma3:4b can't call tools natively (its capabilities: completion, vision), and this role needs tools; add `tool_format: text` to its model entry; nothing was started.
```

In the spike, the same model failed mid-run with an HTTP 400 from Ollama.

## What the failures showed, and what changed

1. **A tool block missing its closing brace (set 1, run 1).**
   - **What happened:** `gemma3:4b` wrote a correct `stage_write` block, except for the final `}`. It stayed invalid through both repair attempts, so the block came back as the final answer, and nothing was written. The verifier failed the run, which is the right outcome. But the report said `done`.
   - **The change:** the parser now closes braces and brackets a model left open, when that is the only problem. The exact block from this run now parses into the intended call (tested in `tests/engine/test_text_tools.py`).
2. **A repetition loop (set 2, run 3).**
   - **What happened:** `gemma3:4b` started the same block correctly, then wrote newlines inside the file's content until it reached its output limit: 15,503 tokens, 280 s. An unterminated string can't be repaired.
   - **The change:** a text-format reply that still holds a tool block is now a failed answer, classified as `error`. The actor falls back to its next model, or reports `failed`, instead of reporting `done`.
   - **Deferred:** capping output tokens per request, so such a loop stops early (`TODO.md`).

Both changes were made after the runs above and are covered by unit tests. They were not re-measured on the real model.

## Spend

Cloud spend: **$0.0021408**, the three Haiku runs, against a cap of $1.00. Local runs cost nothing per token.

## Surprises

- **`gemma3:4b` beat `qwen3.8:27b` on time:** about 9 s against 16 s, when it worked. A small model through the text format is a usable fallback for simple cues.
- **The verifier caught every failure,** including the one the report got wrong. That is why work counts as done only when a verifier says so.
- **Pydantic AI ran several tool calls from one reply concurrently,** so two stage writes could land in either order. Stage tools now run sequentially (found by a flaky test before any real run).
