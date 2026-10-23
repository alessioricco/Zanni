# Roadmap

The first version proves the shape with one play, on machines the maintainer owns. Each milestone is done when its "done when" is met by recorded runs or tests, not by a single impression (golden rule 7).

| # | Milestone | Done when |
|---|---|---|
| 0 | **Scaffold** ✅ | `zanni <file>` validates actor files, play files and role manifests, with errors in plain words. The spec stubs, the conformance suite and CI are in place. |
| 1 | **Spec** | The role package, play folder, actor file and casting extension pages have no Draft sections left for the first version's scope, including the typed encoding (D6). Conformance cases cover every rule. |
| 2 | **Engine adapter: one actor, one model** | `zanni tester.yaml` runs a role from a local folder on one task, against a local stage. It runs on at least one local and one cloud model, with no code change between them. Its cost is reported (D7), and the text tool format works on a model without native tool calling (D5). |
| 3 | **Actor over A2A** | The actor serves an Agent Card built from its role. A cue arrives as an A2A task and runs with polling or streaming. Live tests skip cleanly when no model is configured. |
| 4 | **Director and casting** | `zanni play.yaml` starts a director that casts actors (local seats started by the director, remote ones joining), sends cues from the script, enforces the house rules (budget, seats, gates) and recasts a seat that stops answering. |
| 5 | **Stage as git** | Each seat works on its own branch, its permissions are checked on write, and credentials scoped to the seat are released at the end. This settles the vision's "Stage" open question. |
| 6 | **The software play** | The product owner, architect, UI designer, tester, developer lead, coders and director run one full round. A coding engine works through MCP, and verifiers on the director's side decide what is done. |
| 7 | **Demo** | A short vision ("a habit tracker") runs three rounds unattended, with a published record of each round: backlog, verdicts, cost, and findings that became passing tests. |

Out of scope for the first version: a role registry, actors hosted by other people, plays other than software, high-risk plays, and a web interface (see the vision).
