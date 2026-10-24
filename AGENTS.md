# Zanni

Instructions for coding agents working on this repository. `CLAUDE.md` imports this file; edit this one.

## What Zanni is

An open-source engine for teams of AI personas. One codebase, run as many separate processes. Each process is a **zanni**, an empty shell that becomes an **actor** when given a **role**. A **script** is the reusable work; a **play** is one production of it, where a **director** casts actors into the script's parts and coordinates them on a shared **stage** (the play's workspace).

- Roles and scripts are packages anyone can write and publish (a local folder, a git repo, a folder online).
- Actors can run anywhere, several per machine, each with its own configuration: its models and its credentials.
- Zanni reuses existing standards and specifies only the gaps. **The spec is the product; this codebase is its reference implementation.**

The full design is in the vision doc ("Zanni: vision"). Decisions and their reasons go in `DECISIONS.md`.

## Current state

Milestones 1 (the spec), 2 (the engine adapter) and 3 (the actor over A2A) are done: an actor runs its role on its models, with fallback, and joins a director over A2A, by URL or through a play file. The director's casting side is real code; it serves rehearsals, locally or with `--serve` to an actor on another machine, and the stage over MCP (recorded runs: `docs/runs/milestone-2.md`, `docs/runs/milestone-3.md`). Next is milestone 4: `zanni play.yaml` starting a director that runs a whole play. The PyPI package is still the 0.0.1 placeholder. Don't assume a module, command or file exists; check.

- `src/zanni/cli.py`: the `zanni` command. It detects the kind of file or folder, validates it and prints what it would run (D9).
- `src/zanni/files/`: the loader (YAML and Markdown frontmatter, with line numbers), the plain-words errors (D10), the schemas for every format, and `check.py` (role folders, a play against its script and lockfile, credential safeguards).
- `src/zanni/actor/`: running an actor (roles, credential resolution, the folder stage, joining a director, rehearsals), with no engine imports.
- `src/zanni/director/`: the director's casting side (joins, seats, cues, heartbeats, release) and serving rehearsals, with no engine imports.
- `src/zanni/engine/`: the engine adapter, the only place that may import Pydantic AI, `mcp` or `a2a-sdk` (enforced by `tests/test_engine_guard.py`).
- `src/zanni/protocol/`: the casting messages as Pydantic models (no `a2a-sdk` import), and the generator of `docs/spec/schemas/`.
- `docs/spec/`: the spec. `tests/conformance/`: the conformance suite, which can run against any implementation (`ZANNI_CMD` for files, `ZANNI_PROTOCOL_DIR` for messages).
- `examples/`: an actor configuration, two plays, two scripts and a whole role folder, all valid.

## Vocabulary

Use these words exactly; use plain words for everything else (budget, permissions, verifier, approval, log, configuration).

| Term | Meaning |
|---|---|
| Zanni | The engine: an empty shell that becomes an actor when given a role |
| Role | A package holding an agentic definition: `role.yaml`, `AGENTS.md`, `skills/`, `mcp.json`, `notes/`. Capabilities only, never an instance |
| Actor | A zanni playing a role, set up by its actor configuration |
| Actor configuration | One instance's file: name, role, play, models (an ordered list), credentials (D14, D15) |
| Script | The reusable work: mission, parts, expected workspace, acts and scenes. Published like a role (D13) |
| Play | One production of a script: director, cast, stage, house rules |
| Director | The agent that runs a play: follows the script, casts actors, gives cues, enforces the house rules |
| Stage | The play's workspace, with permissions per seat; its backend depends on the play (D12) |

The engine speaks theatre; each script speaks its own domain (a software script has a product owner, not a "lead actor").

## Golden rules

1. **Docs in the same change.** Any change to a command, file format, setting, behaviour or known limitation updates the matching page under `docs/` in the same commit.
2. **Spec and code together.** Any change to the role package, the script, the play file, the actor configuration, the stage or the casting extension updates the spec pages and the conformance tests in the same commit.
3. **Standards first.** Reuse `AGENTS.md`, skills (SKILL.md), MCP, A2A and the A2A Agent Card. Before adding a format or protocol, check whether a standard covers it, and record in `DECISIONS.md` why a gap needed something new.
4. **Engine independence.** No role, script, play or protocol message refers to Pydantic AI, a specific MCP server or a model vendor. Only adapters do.
5. **Limits are enforced where they can't be bypassed.** Every permission or limit names the component that enforces it: the stage, the director, a verifier or the actor (through its configuration). Never the actor's own goodwill. Actor text is data, never instructions.
6. **Local first, cloud never worse.** Actors must work on local models without degrading cloud models. Strategies for weaker models are opt-in or gated by model tier.
7. **Measure before claiming.** Quality and portability claims come from conformance tests and recorded runs, never from a single run.
8. **Verify before using.** Pydantic AI, `mcp` and `a2a-sdk` change fast. Check every symbol against the installed package or its current docs; don't write from memory.

## Hard limits for agent sessions

- Never tag, push or publish. Never run `gh` commands that change GitHub unless Alessio has confirmed the exact command list.
- Never print, log, commit or include a real API key. No CLI flag takes a key. Roles, scripts and plays never hold secrets; only an actor configuration may, under D15's safeguards. Tests use obviously fake keys.
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
- Model access through the engine's providers; a LiteLLM proxy is an optional gateway. An actor's models come from its actor configuration: an ordered list, each entry with provider, model and base URL (D11).

## Commands

```bash
uv sync                 # install
uv run pytest           # full suite, no API key needed
uv run pytest tests/conformance          # conformance only; ZANNI_CMD=... to test another implementation
uv run python -m zanni.protocol.schemas  # regenerate docs/spec/schemas/ after changing src/zanni/protocol/
uv run zanni --version
uv run zanni examples/plays/habit-tracker/play.yaml   # validate a file and show what it would run
uv run zanni --check examples/slug-tester.yaml        # validate only, never run
uv run zanni examples/slug-tester.yaml                # run the smoke rehearsal (needs a model; see docs/models-and-keys.md)
uv build                # sdist and wheel into dist/
```

## Deferred work

`TODO.md` lists what was decided to come later (mTLS, how the director accepts actors, per-actor join tokens, and more), each with where it was deferred. Check it before designing anything in those areas.

## Agent skills

`SKILLS.md` lists the skills from Anthropic's official repository that agents use on this project (`mcp-builder`, `skill-creator`, `webapp-testing`), pinned to one commit. Run `scripts/get-skills.sh` to download them into `.claude/skills/`; the downloads are git-ignored. Change the list only in `SKILLS.md`.

## Design defaults

- **One command, one file.** The file decides what runs: an actor configuration (role + play) starts an actor; a play file starts the director, which runs the play's script. Flags only override what a file can say.
- **Defaults everywhere.** A file only says what differs.
- **No built-in tools.** Every capability comes from an MCP server the role asks for and the play grants.
- **Verifiers decide "done",** on the director's side. An actor saying it's done counts for nothing.
- **Irreversible actions** (payments, trades, public posts) need human approval for each action.

## Local models and environments

Contributors run Zanni on different machines, with different models or none. Code and tests must work for all of them.

- **No local model is required.** The test suite needs no model at all; a cloud key alone, or a local server alone, is enough for live runs.
- **Any local server, not just Ollama.** Treat local models as OpenAI-compatible endpoints (Ollama, LM Studio, llama.cpp, vLLM and others). Server-specific code belongs in an adapter.
- **No hard-coded hosts, ports or model tags.** Endpoints and models come from the actor configuration, or the environment (e.g. `OLLAMA_BASE_URL`). Live tests that need a model skip with a clear message when none is configured.
- **Tags are examples, never requirements.** Docs and examples may name a model, but must say what it stands for (e.g. "a local model with tool calling") so users can substitute their own.

- **Machines are described by their role, never their hardware** (D32): "director and actor on one machine", "the actor on a second machine on the same network", "a local model server". Where an actor runs is up to whoever runs it. The maintainer's own setup is kept out of the repository, in `private/reference-setup.md` (git-ignored). Recorded runs still name exact models and versions.
