# Roadmap

The first version proves the shape with one script, played on machines the maintainer owns. Each milestone is done when its "done when" is met by recorded runs or tests, not by a single impression (golden rule 7).

| # | Milestone | Done when |
|---|---|---|
| 0 | **Scaffold** ✅ | `zanni <file>` validates actor files (now actor configurations), play files and role manifests, with errors in plain words. The spec stubs, the conformance suite and CI are in place. |
| 1 | **Spec** ✅ | The actor configuration, role package, script, play, stage and casting extension pages have no Draft sections left for the first version's scope, including the typed encoding (D6). Conformance cases cover every rule. Done in two parts: files (prompt 02), then casting (prompt 03). |
| 2 | **Engine adapter: one actor, its models** ✅ | `zanni tester.yaml` runs a role from a local folder on one task, against a local stage, with the models and credentials from its configuration. It runs on at least one local and one cloud model, with no code change between them, and falls back to the next model when one fails. Its cost is reported (D7), and the text tool format works on a model without native tool calling (D5). Met in `docs/runs/milestone-2.md`: the role ran in a rehearsal (D26), the form this milestone settled on. |
| 3 | **Actor over A2A** ✅ | The actor connects to a director, joins with its Agent Card and the join token, follows its seat's task, and answers cues with reports (D21). Messages match the published schemas. Live tests skip cleanly when no model is configured. Met in `docs/runs/milestone-3.md`: an actor joined a served rehearsal from another process and from a second machine, with the stage over MCP (D29, D31). |
| 4 | **Director and casting** ✅ | `zanni play.yaml` starts a director that fetches the play's script, casts actors into its parts (local seats started by the director, remote ones joining), sends cues from the script, enforces the house rules (budget, seats, gates) and recasts a seat that stops answering. Met in `docs/runs/milestone-4.md`: the slug kata ran to done three times each on one machine with local models, on one machine with cloud models, and with an actor joining from a second machine, plus a recast, a rejected gate, budget stops, an unpriced actor and a pause (D33-D42). |
| 5 | **Stage backends** ✅ | The stage operations work on the `git` backend and on one non-git backend, with permissions enforced in one layer above every backend and credentials scoped to the seat released at the end (D12, D43). Met in `docs/runs/milestone-5.md`: the slug kata on git (a branch per run, a commit per write by its seat, pushed at approved gates) and release notes on an MCP stage server, each on local models, cloud models and two machines, with a verifier seat, gates every round, shorter director turns, and once-each runs for unfinished runs under each `push` setting, a failed push, a stage server going away and a part nobody could take (D43-D51). Per-seat branches and merges gave way to shared writes (D44). |
| 6 | **The software script** | A play of the software script runs one full round: the product owner, architect, UI designer, tester, developer lead, coders and director. A coding engine works through MCP, and verifiers on the director's side decide what is done. |
| 7 | **Demo** | A short vision ("a habit tracker") runs three rounds unattended, with a published record of each round: backlog, verdicts, cost, and findings that became passing tests. |

## After the first version

| Milestone | Done when |
|---|---|
| **Connectors** | Roles ask for capabilities by name; actor configurations bind them to MCP servers; connectors are published and versioned packages with a risk tier, and house rules decide which tiers a play allows (see the vision's open question "Connectors"). |

Out of scope for the first version: a role registry, actors hosted by other people, scripts other than software, high-risk scripts, secrets management for cloud-hosted actors, and a web interface (see the vision).
