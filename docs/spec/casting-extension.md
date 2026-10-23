# Casting extension

**Draft. No wire format is specified yet.**

Casting is how an actor joins a play:

1. **Join:** the actor connects to the director and presents its A2A Agent Card, built from its role.
2. **Casting:** the director checks the actor's role against the part it is cast for, assigns a seat, and sends the stage's MCP address and credentials scoped to that seat ([Stage: transport](stage.md#transport-how-actors-reach-the-stage)).
3. **Cues and reports:** the director sends cues as A2A tasks, and the actor reports back. Heartbeats run in between.
4. **Release:** the director ends the seat and revokes its credentials.

Everything except casting and permissions is plain A2A, through the official `a2a-sdk` (D2).

## What the spike showed (D6)

- **The card can carry the role.** A role's `needs`, `never` and `model.needs` fit in an Agent Card extension (`AgentCapabilities.extensions`), and nested lists and maps arrived intact at the director. The spike used the provisional URI `https://zanni.dev/a2a/ext/role/v0`.
- **Numbers need a typed encoding.** Extension `params` are a protobuf `Struct`, which has no integer type, so every number arrives as a float. Seat counts, budgets and costs need an encoding still to be designed (for example, decimal strings with a declared unit), checked when an actor joins.
- **Cues can't be one long request.** A cue can take minutes on a local model, and the a2a client's default HTTP timeout is 5 s. Cues must be A2A tasks with polling or streaming.

## Still to specify

- **URIs:** the extension URI(s) and versioning.
- **Card fields:** the role fields on the card, with types, using the typed encoding above.
- **Join and release:** the casting messages, including how a refusal is reported back to the actor.
- **Credentials:** how the seat's stage credentials (D16) are delivered and revoked. They are the director's to give, and never the actor's own credentials, which stay in its configuration (D15).
- **Heartbeats:** heartbeats and recasting a seat whose actor stopped answering.
