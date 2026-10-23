# Roadmap

The first version proves the shape with one script, played on machines the maintainer owns. Each milestone is done when its "done when" is met by recorded runs or tests, not by a single impression (golden rule 7).

| # | Milestone | Done when |
|---|---|---|
| 0 | **Scaffold** ✅ | `zanni <file>` validates actor files (now actor configurations), play files and role manifests, with errors in plain words. The spec stubs, the conformance suite and CI are in place. |
| 1 | **Spec** | The actor configuration, role package, script, play, stage and casting extension pages have no Draft sections left for the first version's scope, including the typed encoding (D6). Conformance cases cover every rule. Done in two parts: files (prompt 02) ✅, then casting (prompt 03). |
| 2 | **Engine adapter: one actor, its models** | `zanni tester.yaml` runs a role from a local folder on one task, against a local stage, with the models and credentials from its configuration. It runs on at least one local and one cloud model, with no code change between them, and falls back to the next model when one fails. Its cost is reported (D7), and the text tool format works on a model without native tool calling (D5). |
| 3 | **Actor over A2A** | The actor serves an Agent Card built from its role. A cue arrives as an A2A task and runs with polling or streaming. Live tests skip cleanly when no model is configured. |
| 4 | **Director and casting** | `zanni play.yaml` starts a director that fetches the play's script, casts actors into its parts (local seats started by the director, remote ones joining), sends cues from the script, enforces the house rules (budget, seats, gates) and recasts a seat that stops answering. |
| 5 | **Stage backends** | The stage operations work on the `git` backend (a branch per seat, permissions checked on write, merges by the director) and on one non-git backend, with credentials scoped to the seat released at the end (D12). |
| 6 | **The software script** | A play of the software script runs one full round: the product owner, architect, UI designer, tester, developer lead, coders and director. A coding engine works through MCP, and verifiers on the director's side decide what is done. |
| 7 | **Demo** | A short vision ("a habit tracker") runs three rounds unattended, with a published record of each round: backlog, verdicts, cost, and findings that became passing tests. |

## After the first version

| Milestone | Done when |
|---|---|
| **Connectors** | Roles ask for capabilities by name; actor configurations bind them to MCP servers; connectors are published and versioned packages with a risk tier, and house rules decide which tiers a play allows (see the vision's open question "Connectors"). |

Out of scope for the first version: a role registry, actors hosted by other people, scripts other than software, high-risk scripts, secrets management for cloud-hosted actors, and a web interface (see the vision).
