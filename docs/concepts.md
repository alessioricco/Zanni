# Concepts

Zanni runs a team of AI personas as separate processes. Each persona works on its own and shares only what is on the stage. Its work is checked by verifiers it doesn't control.

The name comes from the zanni, the servant characters of the commedia dell'arte: they did the work, each playing whatever character the scenario needed.

> **Status:** this page describes the design. Today only the file formats exist; the [roadmap](../ROADMAP.md) shows when each part arrives.

## Five words

The engine uses five words from the theatre, and plain words for everything else (budget, permissions, verifier, approval, log):

| Term | Meaning | Example |
|---|---|---|
| **Role** | A folder describing a persona: character, skills, tools, permissions | `roles/tester` |
| **Actor** | A running instance of the engine, bound to one role | the tester, running on a cloud server |
| **Director** | The process that starts a play, casts the actors and coordinates them. It is itself an actor, playing the director role. | one per play |
| **Stage** | The play's shared state, with permissions for each seat | the vision, the backlog, the app's repo |
| **Play** | A project folder: the cast, the script and the stage | `plays/habit-tracker` |

Each play speaks its own domain: the software play has a product owner and an architect, not a "lead actor".

## How a play runs

1. **Start the director.** You start the director with the play file: `zanni play.yaml`. Seats marked `host: local` are started by the director itself, so one command can run a whole play on one machine.
2. **Actors join.** An actor starts from a small actor file that names its role and its play: `zanni tester.yaml`. It connects to the director and presents a card built from its role.
3. **Casting.** The director checks the role against the play's cast and assigns a seat. It then sends the actor the play, where the stage is, and credentials scoped to that seat.
4. **Cues and reports.** The director follows the script and sends cues. Each actor works on the stage and reports back. Actors never read the whole script, only their cue.
5. **Release.** The director ends each seat and revokes its credentials. If an actor stops answering, the director recasts its seat; the work survives on the stage.

Actors can run anywhere: a laptop, a GPU workstation, a cloud server. Several can share one machine. Each actor brings its own model and keys, and the director never holds anyone's keys.

## Roles are packages

A role is a folder that anyone can write, version and publish, like a skill:

```
roles/tester/
  role.yaml    # Zanni's fields: needs, never-rules, outputs
  AGENTS.md    # character and instructions
  skills/      # skills in SKILL.md format
  mcp.json     # the MCP servers it expects
  notes/       # lessons, private to the role
```

- **References:** a play refers to a role by URL and version (`github.com/someone/tester@1.4.0`), or by a local folder.
- **Needs:** a role's needs are requests. The play grants them or not.
- **Tools:** Zanni has no built-in tools. Everything an actor can do comes from an MCP server that its role asks for and its play grants.

See [Writing a role](writing-a-role.md).

## Limits are enforced where they can't be bypassed

Actors may run on machines the play's owner doesn't control, so no limit depends on an actor obeying it:

| Limit | Enforced by |
|---|---|
| What a seat can read and write | The stage |
| Budget, number of seats, human approvals | The director, under the house rules |
| What counts as done | Verifiers, on the director's side |
| An actor's own spend, and which directors it joins | The actor's host |

The house rules are set when the director starts. No role, script or actor can loosen them.

What an actor writes is data, never instructions: it may carry text injected from a web page or a repo. An irreversible action, such as a payment or a public post, always needs a human's approval for that action.

## Work is done when a verifier says so

An actor saying its work is done counts for nothing. Every play brings verifiers that don't depend on any actor's opinion, such as the project's tests on the merged code, or browser tests on the running app. Results say which kind of verifier produced them: hard or soft.

## Built on standards

| Need | Standard |
|---|---|
| A role's character and instructions | `AGENTS.md` |
| A role's skills | SKILL.md ([Agent Skills](https://agentskills.io)) |
| A role's tools | MCP |
| Director-to-actor messages | A2A |
| An actor's card when it joins | A2A Agent Card |

Zanni specifies only what these standards don't cover. That is [the spec](spec/README.md), and it is the product: this codebase is its reference implementation, so others can build their own.
