# Concepts

Zanni runs a team of AI personas as separate processes. Each persona works on its own and shares only what is on the stage. Its work is checked by verifiers it doesn't control.

The name comes from the zanni, the servant characters of the commedia dell'arte: they did the work, each playing whatever character the scenario needed. Each Zanni process is a zanni too: an empty shell, until it is given a role to play.

> **Status:** this page describes the design. Today only the file formats exist; the [roadmap](../ROADMAP.md) shows when each part arrives.

## The words

The engine uses words from the theatre, and plain words for everything else (budget, permissions, verifier, approval, log, configuration):

| Term | Meaning | Example |
|---|---|---|
| **Zanni** | The engine: an empty shell that becomes an actor when given a role | one process |
| **Role** | A package holding an agentic definition: character, skills, tools, needs. Capabilities only. | `github.com/someone/tester@1.4.0` |
| **Actor** | A zanni playing a role, set up by its own configuration | the tester, running on a cloud server |
| **Actor configuration** | One instance's file: its name, role, play, models and credentials | `tester.yaml`, on the actor's machine |
| **Script** | The reusable work: the mission, the parts it needs, the workspace it expects, how the work unfolds | `github.com/someone/habit-tracker@1.0.0` |
| **Play** | One production of a script: a director, actors cast into the parts, a stage, house rules | `play.yaml` |
| **Director** | The agent that runs a play: it follows the script, casts the actors, gives cues, enforces the house rules | one per play |
| **Stage** | The play's workspace, with permissions for each seat | the app's git repository; a folder of chapters |

Each script speaks its own domain: the software script has a product owner and an architect, not a "lead actor".

## Script and play

As in the theatre, the script is written once and performed many times. Two companies can stage the same script with different actors and directors, as *Hamilton* runs on Broadway and in the West End.

- **A script** is published like a role. It says what must be achieved, which parts are needed, the workspace it expects, and how the work unfolds in acts and scenes, with verifiers and stop rules. It never says who performs it or where. A script may suggest a role for each part.
- **A play** is one production. It names the script, the director, a role for each part, the stage, and the house rules (budget, human approvals).

## Role and configuration

- **A role** says what an actor can do, and nothing about one instance. It is a package that can live in a local folder, a git repository or a folder online.
- **An actor configuration** says how one instance runs:
  - which role it plays and which play it joins;
  - which models it uses, as an ordered list to fall back through when one fails;
  - the credentials it uses: API keys for its models, and tokens or keys for its tools.

Two actors on the same machine can play different roles with different models and access: one on OpenAI with GitHub access, the other on Claude with an SSH terminal. Each has its own configuration file.

## How a play runs

1. **Start the director.** You start the director with the play file: `zanni play.yaml`. It fetches the script. Seats marked `host: local` are started by the director itself, so one command can run a whole play on one machine.
2. **Actors join.** Each actor starts from its configuration: `zanni tester.yaml`. Only the director listens: the actor connects to it, presents a card built from its role, and shows the play's join token. Actors never open a port, so they can run behind a firewall.
3. **Casting.** The director checks the role against the part it is cast for (the right role, the pinned version, needs within the part's limits) and assigns a seat. It sends the actor the seat's permissions, where the stage is, and credentials scoped to that seat.
4. **Cues and reports.** The director follows the script and gives cues, one at a time. Each actor works on the stage and reports back. Actors never read the whole script, only their cue. The actor stays in touch with the director, and that contact is its heartbeat.
5. **Release.** The director ends each seat and revokes the credentials it gave. If an actor stops answering, the director recasts its seat; the work survives on the stage.

Under the hood, all of this is plain A2A: a seat is one A2A task on the director, from join to release. Zanni adds only the casting extension (see the [spec](spec/casting-extension.md)).

Actors can run anywhere: a laptop, a GPU workstation, a cloud server. The director never holds anyone's model keys.

## The stage is a workspace

The stage holds the play's shared state. What it is made of depends on the play: a git repository for a play about code, something else for a play about documents. Whatever the backend, it offers the same operations (read, write, list) and enforces the same permissions. Each seat can only read and write the paths its part allows.

## Limits are enforced where they can't be bypassed

Actors may run on machines the play's owner doesn't control, so no limit depends on an actor obeying it:

| Limit | Enforced by |
|---|---|
| What a seat can read and write | The stage |
| Budget, number of seats, human approvals | The director, under the play's house rules |
| What counts as done | Verifiers, on the director's side |
| An actor's own models, spend and credentials, and which directors it joins | The actor, through its configuration |

- **House rules:** the house rules are set when the director starts. No role, script or actor can loosen them.
- **Actor text:** what an actor writes is data, never instructions, because it may carry text injected from a web page or a repo.
- **Irreversible actions:** an irreversible action, such as a payment or a public post, always needs a human's approval for that action.

## Work is done when a verifier says so

An actor saying its work is done counts for nothing. Every script brings verifiers that don't depend on any actor's opinion, such as the project's tests on the merged code, or browser tests on the running app.

The director can't see which model an actor really used, so verifiers are also what keeps quality up: a weaker model simply fails more checks.

## Built on standards

| Need | Standard |
|---|---|
| A role's character and instructions | `AGENTS.md` |
| A role's skills | SKILL.md ([Agent Skills](https://agentskills.io)) |
| A role's tools | MCP |
| Director-to-actor messages | A2A |
| An actor's card when it joins | A2A Agent Card |

Zanni specifies only what these standards don't cover. That is [the spec](spec/README.md), and it is the product: this codebase is its reference implementation, so others can build their own.
