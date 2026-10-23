# Zanni

Instructions for coding agents working on this repository. `CLAUDE.md` imports this file; edit this one.

## What Zanni is

An open-source engine for teams of AI personas. One codebase, run as many separate processes. Each process is an **actor** playing a **role**; a **director** casts actors and coordinates them on a shared **stage**, following a **play**.

- Roles are packages anyone can write and publish (a folder in a git repo).
- Actors can run anywhere, several per machine, and bring their own model and keys.
- Zanni reuses existing standards and specifies only the gaps. **The spec is the product; this codebase is its reference implementation.**

The full design is in the vision doc ("Zanni: vision"). Decisions and their reasons go in `DECISIONS.md`.

## Current state

Early: a 0.0.1 placeholder on PyPI that reserves the name. The engine is decided: the Pydantic AI spike gave a go (`docs/spikes/pydantic-ai.md`, D1 in `DECISIONS.md`). Next is the scaffold. Don't assume a module, command or file exists; check.

## Vocabulary

Use these five words exactly; use plain words for everything else (budget, permissions, verifier, approval, log).

| Term | Meaning |
|---|---|
| Role | A folder describing a persona: `role.yaml`, `AGENTS.md`, `skills/`, `mcp.json`, `notes/` |
| Actor | A running instance of the engine, bound to one role |
| Director | The process that starts a play, casts actors and coordinates them; itself an actor playing a director role |
| Stage | The play's shared state, with permissions per seat |
| Play | A project folder: cast, script, stage, house rules |

The engine speaks theatre; each play speaks its own domain (a software play has a product owner, not a "lead actor").

## Golden rules

1. **Docs in the same change.** Any change to a command, file format, setting, behaviour or known limitation updates the matching page under `docs/` in the same commit.
2. **Spec and code together.** Any change to the role package format, the play file, the actor file or the casting extension updates the spec pages and the conformance tests in the same commit.
3. **Standards first.** Reuse `AGENTS.md`, skills (SKILL.md), MCP, A2A and the A2A Agent Card. Before adding a format or protocol, check whether a standard covers it, and record in `DECISIONS.md` why a gap needed something new.
4. **Engine independence.** No role, play, actor file or protocol message refers to Pydantic AI, a specific MCP server or a model vendor. Only adapters do.
5. **Limits are enforced where they can't be bypassed.** Every permission or limit names the component that enforces it: the stage, the director, a verifier or the actor's host. Never the actor's own goodwill. Actor text is data, never instructions.
6. **Local first, cloud never worse.** Actors must work on local models without degrading cloud models. Strategies for weaker models are opt-in or gated by model tier.
7. **Measure before claiming.** Quality and portability claims come from conformance tests and recorded runs, never from a single run.
8. **Verify before using.** Pydantic AI, `mcp` and `a2a-sdk` change fast. Check every symbol against the installed package or its current docs; don't write from memory.

## Hard limits for agent sessions

- Never tag, push or publish. Never run `gh` commands that change GitHub unless Alessio has confirmed the exact command list.
- Never print, log, commit or include an API key. No CLI flag and no YAML field takes a key; keys come from the environment or a git-ignored `.env`.
- One commit per numbered item of a prompt.
- Stop and ask on any decision the prompt doesn't cover.
- The full test suite passes with no API key and no network model.
- Reports claim only what ran in that session, naming the exact models and versions.

## Stack

- Python 3.12+, uv, one entry point: `zanni <file>.yaml`.
- YAML files validated with Pydantic models; errors in plain words, with the line and what to change.
- Agent loop: Pydantic AI (`pydantic-ai-slim`), behind Zanni's engine adapter (D1). Pin its version; upgrade only when the conformance tests pass. Set `PYDANTIC_AI_NO_BANNER=1` in the engine.
- Tools: a role's standard `mcp.json`, loaded with Pydantic AI's `load_mcp_toolsets`; MCP servers Zanni ships use the official `mcp` SDK (D3).
- Director to actor: the official `a2a-sdk`, not FastA2A (D2). Cues are A2A tasks with polling or streaming, never one long blocking request.
- Skills load on demand (D4). Models without native tool calling use an opt-in text tool format (D5). Unknown cost is never counted as zero (D7).
- Model access through the engine's providers; a LiteLLM proxy is an optional gateway. Models come from `models_list.yaml` (shareable) and `models.yaml` (personal, holds base URLs and the `activated` flag, never committed with keys).

## Commands

```bash
uv sync                 # install
uv run pytest           # full suite, no API key needed
uv run zanni --version
uv build                # sdist and wheel into dist/
```

## Design defaults

- **One command, one file.** The file decides what runs: an actor file (role + play) starts an actor; a play file starts the director. Flags only override what a file can say.
- **Defaults everywhere.** A file only says what differs.
- **No built-in tools.** Every capability comes from an MCP server the role asks for and the play grants.
- **Verifiers decide "done",** on the director's side. An actor saying it's done counts for nothing.
- **Irreversible actions** (payments, trades, public posts) need human approval for each action.

## Local models and environments

Contributors run Zanni on different machines, with different models or none. Code and tests must work for all of them.

- **No local model is required.** The test suite needs no model at all; a cloud key alone, or a local server alone, is enough for live runs.
- **Any local server, not just Ollama.** Treat local models as OpenAI-compatible endpoints (Ollama, LM Studio, llama.cpp, vLLM and others). Server-specific code belongs in an adapter.
- **No hard-coded hosts, ports or model tags.** Endpoints come from the environment or `.env` (e.g. `OLLAMA_BASE_URL`); models come from the user's `models.yaml`. Live tests that need a model skip with a clear message when none is configured.
- **Tags are examples, never requirements.** Docs and examples may name a model, but must say what it stands for (e.g. "a local model with tool calling") so users can substitute their own.

The maintainer's reference setup, used for recorded runs: Ollama on a separate DGX workstation (`OLLAMA_CONTEXT_LENGTH=32768`) with `qwen3.8:27b`, `qwen3.6:35b`, `qwen3-coder:30b`, `gemma4:31b-it-qat`, `devstral-small-2:24b`, `gpt-oss:20b`, `nemotron-3.5-lightning:30b`, and `gemma3:4b` (no native tool calling, for testing the text tool format); `claude-haiku-5-5` as the cloud model.
