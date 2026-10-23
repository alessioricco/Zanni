# Zanni: vision

Working name · Oct 22, 2026, updated Oct 23, 2026 · @Alessio

## Summary

Zanni is an open-source engine for running teams of AI personas. The zanni were the servant characters of the commedia dell'arte, the ones who did the work, each playing whatever character the scenario needed. It is one codebase, run as many separate processes. Each process is an actor playing a role, and a role is a folder: character, skills, tools and permissions.

A director starts a play, casts the actors, tells them where the stage is and what the play is, and coordinates them. Roles are packages anyone can write and publish on GitHub. Actors can run on any machine, local or remote.

Zanni is built on existing standards (MCP, A2A, AGENTS.md, skills) and specifies only what they don't cover. The spec is the product; this codebase is its reference implementation, so others can build better ones. The first play is a software team.

## Why

An agent's work is more trustworthy when something other than the agent checks it. Larger work, such as a product, an article series or a novel, needs several perspectives: someone who decides what to build, someone who designs it, someone who tests it.

Today that is usually one agent playing every part in one context. It grades its own work, and its context fills up. Zanni separates the parts: each persona runs on its own, shares only what is on the stage, and is checked by verifiers it doesn't control.

Goals:

- Personas are configuration, not code: the same engine plays any role.
- Roles are shareable: people write them, publish them and improve each other's.
- Actors run anywhere: a laptop, a GPU workstation, a cloud server.
- Limits are set by whoever runs the play, and no role can loosen them.
- Work counts as done only when a verifier says so.

## Experience

Running Zanni must feel effortless: one command, one file. Everything else lives in configuration.

```
zanni tester.yaml
```

An actor file says which role to play, and in which play:

```yaml
# tester.yaml
role: github.com/someone/tester@1.4.0
play: https://example.com/plays/habit-tracker/play.yaml
```

A play file holds everything needed to start working: the director, the stage, the cast, the script and the house rules.

```yaml
# play.yaml
name: habit-tracker
director: wss://director.example.com
stage: git@github.com:alessio/habit-tracker.git
script: ./script.yaml
cast:
  product-owner: github.com/zanni-roles/product-owner@1.0.0
  tester: github.com/someone/tester@1.4.0
  coder: { role: github.com/zanni-roles/coder@1.0.0, seats: 1-4, host: local }
house_rules:
  budget: 20.00
  gates: [plan, release]
```

- **The file decides what runs.** `zanni play.yaml` starts the director; `zanni tester.yaml` starts an actor that joins it. Same command, same binary.
- **A whole play on one machine.** Seats marked `local` are started by the director itself, so `zanni play.yaml` alone can run a play on a laptop.
- **Defaults everywhere.** Models, ports, state folders and timeouts have sensible defaults; a file only says what differs.
- **No secrets in files.** API keys come from the environment or a `.env`, never from a YAML file.
- **Errors in plain words.** A bad file is rejected before anything starts, with the line and what to change.
- **Flags only override.** Anything a flag can set, a file can set; nothing requires a flag.

## Vocabulary

Five core nouns come from the theatre; everything else uses plain words (budget, permissions, verifier, approval, log). The engine speaks theatre; each play speaks its own domain, so the software play has a product owner and an architect.

| Term | Meaning | Example |
| --- | --- | --- |
| Role | A folder describing a persona: character, skills, tools, permissions | `roles/tester` |
| Actor | A running instance of the engine, bound to one role | the tester, running on a cloud server |
| Director | The process that starts a play, casts actors and coordinates them; itself an actor playing `roles/director` | one per play |
| Stage | The play's shared state, with permissions per seat | vision, backlog, the app's repo |
| Play | A project folder: the cast, the script and the stage | `plays/habit-tracker` |

## Spec and standards

Zanni reuses an existing standard wherever one fits, and specifies only the gaps. The spec (formats, protocol, conformance tests) is the product; this codebase is its reference implementation.

| Need | Standard |
| --- | --- |
| A role's character and instructions | `AGENTS.md` (a `CLAUDE.md` may point to it) |
| A role's skills | Skills in the SKILL.md format |
| The tools a role uses | MCP, with the standard server config |
| Director-to-actor messages | A2A |
| An actor's manifest when it joins | An A2A Agent Card, built from its role |

What Zanni adds, as extensions to those standards:

- the role fields no standard covers: stage permissions, never-rules, outputs, budget;
- the play folder: cast, script, stage, log, lockfile;
- casting: join, seat, credentials scoped to the seat, release;
- conformance tests, so another implementation can prove it runs the same roles and plays.

## Roles

A role is a folder anyone can write, version and publish, like a skill. The engine reads it; no code changes to add a role.

```
roles/tester/
  role.yaml       # Zanni fields: needs, never-rules, outputs, budget
  AGENTS.md       # character and instructions (CLAUDE.md may point here)
  skills/         # skills in SKILL.md format
  mcp.json        # MCP servers it expects, standard config format
  notes/          # curated lessons, private to the role
```

An example manifest:

```yaml
name: tester
version: 1.4.0
mission: Turn acceptance criteria into tests; explore the running app and report findings.
model: { needs: { tools: true, tier: judgement }, suggested: claude-sonnet-5-5 }
needs:
  stage_read: [vision.md, backlog/, spec/]
  stage_write: [tests/, findings/]
  tools: [browser, test-runner]
never:
  - edit application code
  - change priorities
outputs:
  findings/<item>.md: one finding per file, each with a failing test
```

- **Needs are requests, not grants.** A role declares what it needs; the play grants it or not.
- **Roles are packages.** A role lives in a repo, or a folder in one, and is referenced by URL and version (`github.com/someone/tester@1.4.0`). A play pins each role to a commit in a lockfile.
- **Roles from other people are untrusted** until the play grants their needs, and they run sandboxed.
- **Some roles are thin.** A coder is mostly a workstream (the paths it owns), conventions, and an MCP config pointing at a coding engine: any MCP server that changes code and runs its tests.

## Plays

A play is a folder that holds what the actors do together: who is cast, what the script is, and the stage they share.

```
plays/habit-tracker/
  play.yaml     # cast: roles, seats per role, limits, human gates
  roles.lock    # each role resolved to a commit
  script.yaml   # acts and scenes: who hands off to whom, loops, stop rules
  stage/        # shared state: vision, spec, backlog, tests, the app's repo
  log/          # who did what, verifier results, costs
```

- **The cast** lists roles and seats. A seat can be a range (`coder: 1-4`); the director decides how many within it.
- **The script** is the workflow. The director reads it and gives cues; actors never read the whole script, only their cue.
- **The stage** holds shared state only. Each actor's working memory stays private and is discarded when its task ends.
- **The log** records every cue, result, verdict and cost, so a returning human can see what happened.

## Director and actors

Every actor is a separate process running the same engine. It starts from one small file naming its role and its play; the play says where the director is, and the director tells it everything else.

```
zanni tester.yaml
```

1. **Join.** The actor connects and presents its A2A Agent Card, built from its role.
2. **Casting.** The director checks the role against the play's cast, assigns a seat, and sends the play, the stage's location and credentials scoped to that seat.
3. **Cues and reports.** The director sends a cue; the actor works on the stage and reports back. Heartbeats run in between.
4. **Release.** The director ends the seat and revokes its credentials.

- **Actors bring their own model and keys.** A coder on a GPU workstation runs a local model; an architect on a cloud server runs a cloud model. The director never holds anyone's API keys. Several actors can run on one machine, each with its own state folder and port; the director knows which actors share a host and caps local-model seats per host, since they share its GPU.
- **Failure is ordinary.** If an actor stops answering, the director recasts its seat. The work survives on the stage.
- **The director is a role too,** played by the same engine. It is the only role allowed to cast and release actors.
- **Protocols:** MCP for actor-to-tools, A2A for director-to-actor. Only casting and permissions are Zanni's own, as an A2A extension.

## Models and stack

Actors are model- and provider-agnostic: no role, actor or play depends on a specific model or vendor.

A role states what it needs, and may suggest a default:

```yaml
model:
  needs: { tools: true, context: 32k, tier: judgement }
  suggested: claude-sonnet-5-5
```

- **The actor's host picks the model,** matching the role's needs against its own catalog. It uses two files: a shareable `models_list.yaml` (ratings, ladders) and a personal `models.yaml` (keys, base URLs, the `activated` flag). The same role runs on a local model on one host and a cloud model on another.
- **No vendor tricks in role files.** `AGENTS.md`, skills and prompts are plain Markdown. When a model can't call tools natively, the actor falls back to a text-based tool format; the fallback is opt-in, so cloud models aren't made worse.
- **Escalation per seat.** A seat can have a ladder: start on a local model, climb to a cloud one when the seat fails, with the director counting the cost.
- **Proved by tests.** Conformance tests run each reference role on at least one local and one cloud model.

The stack:

| Layer | Choice |
| --- | --- |
| Language | Python 3.12+, uv, one `zanni` entry point |
| Model access | Pydantic AI's providers (Ollama, OpenAI-compatible endpoints, the main cloud APIs); a LiteLLM proxy as an optional shared gateway |
| Agent loop | Pydantic AI, behind Zanni's engine adapter |
| Tools | MCP: a role's `mcp.json` loaded by Pydantic AI's MCP client; MCP servers written by Zanni use the official `mcp` SDK |
| Director to actor | The official `a2a-sdk` (not FastA2A), with role fields in an Agent Card extension |
| Configuration | YAML, validated with Pydantic models |

Pydantic AI was chosen because it is independent of any model vendor and has the largest community, and confirmed by a spike in October 2026 (`docs/spikes/pydantic-ai.md`): the same actor ran on a local and a cloud model with no code change, loaded its tools from a standard `mcp.json`, and reported its cost. It runs behind a thin engine adapter, so roles, plays and the protocol never mention it and another engine could replace it. Pydantic AI versions are pinned and upgraded only when the conformance tests pass.

Zanni adds what Pydantic AI doesn't provide:

- loading `AGENTS.md`, and skills on demand;
- the A2A layer: Agent Card, executor, casting extension;
- the text-based tool fallback for models without native tool calling, as an opt-in wrapper model;
- detecting what a local model server supports, so a missing capability is caught before a run;
- cost per seat and the play's budget: unknown costs are never counted as zero, and local models get a price declared by their host.

## Trust model

Actors may run on machines the play's owner doesn't control, so no limit depends on an actor obeying it. Each limit is enforced where it can't be bypassed.

| Limit | Enforced by |
| --- | --- |
| What a seat can read and write | The stage |
| Budget, number of seats, human gates | The director, under the house rules |
| What counts as done | Verifiers on the director's side |
| Its own spend, and which directors it will join | The actor's host |

- **House rules** are set when the director starts. No role, script or actor can loosen them.
- **Risk tiers:** read, spend, external action, irreversible. An irreversible action (a payment, a trade, a public post) always needs human approval for each action.
- **Actor text is data, never instructions.** What an actor writes may carry injected instructions from a page or a repo; other actors and the director treat it as content.
- **Domain safety rules live in the engine,** not in role files. A wellbeing play, for example, gets crisis handling that no role can remove.

## Verification

An actor saying its work is done counts for nothing. Every play brings verifiers: checks that don't depend on any actor's opinion, run on the director's side.

| Play | Verifiers | Kind |
| --- | --- | --- |
| Software team | The project's tests on the merged code, browser tests on the running app | Hard |
| Article writing | Fact checks against cited sources, links that resolve, style lint, length | Mixed |
| Novel writing | Continuity against a story bible: names, timeline, who knows what | Soft |
| Trading | Backtests and paper trading before any real order | Hard, but not a guarantee |

Results say which kind of verifier produced them. Opinions found by an actor, such as a tester's finding, count once they become something a verifier can run.

## Tools

Zanni has no built-in tools and depends on no particular MCP server. Every capability an actor has comes from an MCP server its role asks for and its play grants: a browser, a test runner, a search tool, a coding engine.

- **A coder role asks for a coding engine:** any MCP server that changes code and runs its tests. Which one is the play's or the actor host's choice.
- **What a play needs from a tool belongs in that tool,** not in Zanni. Zanni only needs MCP.

## First play: the software team

The first play turns a vision document into a working app, in rounds, with a coding engine doing the coding and verifiers checking the work.

| Role | Writes | Never |
| --- | --- | --- |
| Product owner | Backlog, priorities, acceptance criteria, roadmap | Writes code or tests; marks work done |
| Architect | Architecture, module boundaries, API contracts, data model | Changes scope or priorities |
| UI designer | Screens, flows, design system | Changes scope or priorities |
| Tester | Tests from acceptance criteria; findings from exploring the app | Fixes bugs; reads the coders' reasoning |
| Developer lead | Tasks for coders, worktree merges | Edits tests to make them pass |
| Coder (1 to N) | Code in its workstream, through a coding engine | Touches another workstream's paths |
| Director | Cues, casting, the log | Does any of the work itself |

One round:

1. The product owner picks the round's items; the human approves the plan.
2. The architect and the UI designer write the spec; the tester writes tests from the acceptance criteria.
3. The developer lead groups tasks by workstream and the director casts that many coders.
4. Each coder runs its tasks through its coding engine; a `verified` task closes its item.
5. The developer lead merges the worktrees; the verifiers run the tests on the combined code and the browser tests on the app.
6. The tester explores the running app; every bug becomes a failing test and a backlog item.
7. The product owner reviews against the vision and plans the next round.

- **Human gates:** the vision, each round's plan, and each release.
- **Models by role:** a strong model for judgement roles (product owner, architect, designer); local models for coders, with escalation as the safety net.
- **Stop rules:** a round budget, a maximum number of rounds, and stopping when a round adds no verified items.

## First version

The first version proves the shape with one play on machines Alessio owns, before opening it to other people's roles and hosts.

In scope:

- one director and several actors as separate processes, on a laptop and the DGX workstation;
- roles from local folders and git URLs, pinned in a lockfile;
- a stage as a git repo, with a branch per seat and permissions checked on write;
- house rules: budget, seats, human gates;
- the spec first (role package format, play folder, the A2A extension for casting and permissions, conformance tests), then the software team play, with a coding engine through MCP;
- Zanni's working agreements: docs in the same change, measure before claiming, prompts don't publish.

Out of scope for now:

- a registry or marketplace of roles;
- actors hosted by other people;
- plays other than software (article writing comes next, as the test that the engine is really generic);
- high-risk plays such as trading or wellbeing, until risk tiers and approvals are proven;
- a web interface.

**Demo that marks it done:** a short vision ("a habit tracker"), three rounds unattended, and a published record of each round: backlog, verdicts, cost, and findings that became passing tests.

## Open questions

- [ ] Name: "Zanni". Reserved on PyPI (0.0.1) and GitHub (`alessioricco/zanni`); a domain is still to check.
- [x] A2A fit: yes. The spike carried a role's needs, never-rules and model needs in an Agent Card extension, intact. Caveat: extension params are a protobuf `Struct` with no integer type, so seat counts and budgets need a typed encoding (D6 in `DECISIONS.md`).
- [ ] Stage: a git repo with a branch per seat, or a service with an API in front of the files?
- [ ] Who merges the coders' worktrees: the developer lead, the director, or the coding engine?
- [x] Pydantic AI spike: go (D1). There is no built-in fallback for models without native tool calling, and a 64-line wrapper model is enough for one. Pydantic AI has no A2A support of its own, and FastA2A (now `datalayer/fasta2a`) is not used (D2).
- [ ] Who chooses the model: the role's default, the play, or the actor's host?
- [x] Licence: MIT.
