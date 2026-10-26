# To do

Things decided to come later. Each names where it was deferred. Remove an item when it is done, or when a decision replaces it.

## Security

- [ ] **mTLS between actors and the director.** The first version uses bearer tokens: a join token, then tokens scoped to each seat (D24). Replace or back them with mutual TLS, once there are certificates to manage. Deferred at casting ask point C ("make it work, then make it better").
- [ ] **How the director accepts an actor.** Today a valid join token and a role that fits a free part are enough (D21, D24). Decide whether joins need a human's approval, an allowlist of actors or roles, or a policy in the play's house rules. Deferred at casting ask point A.
- [ ] **One join token per actor.** The first version shares one join token per play (`ZANNI_JOIN_TOKEN`). Per-actor tokens would let a director revoke one actor without the rest.
- [ ] **Secrets management for actors on cloud services** (D15).
- [ ] **Renewing seat tokens.** A cast's tokens expire after 24 hours, and the spec allows renewing them with a new cast message, but the director doesn't renew them yet, so a seat ends at `expires_at`. Deferred in milestone 3.
- [ ] **TLS for the director.** `--serve` speaks plain HTTP, so tokens cross the network in the clear. Put it behind a TLS proxy on untrusted networks, until the director serves HTTPS itself (with mTLS, above). Deferred in milestone 3.
- [ ] **Sandboxing a rehearsal's `verify` commands, a script's verifiers**, and a role's MCP servers, for roles and scripts from other people. Today they run with the user's permissions (D26, D35).
- [ ] **An app started in a workspace can take the director's address.** On macOS, a server listening on `127.0.0.1:<port>` takes that address from a director listening on `0.0.0.0:<port>`: in milestone 6's two-machine run, the app a tester started for exploring answered the seats on the director's machine in its place, and a seat lost its cue. A workspace's commands share the machine's network; a sandbox per workspace, or local seats reaching the director by an address no command can take, would close it (D52).
- [ ] **Containing a workspace's commands.** `workspace.commands` limits which commands start, not what they do: `uv run python` can write outside the workspace, or start a process that leaves its group. In milestone 6's recorded runs, a tester exploring the app left it running for hours, and an engine an actor brought wrote two files in `/tmp`. Zanni now stops everything in a command's process group when the cue ends, but a process that leaves its group, or a file written elsewhere, isn't caught; a sandbox per workspace is the real limit (D52, D53).
- [ ] **Checking signed tags** when fetching packages. Deferred at milestone 4's ask point E (D37).
- [ ] **An actor's own spending cap**, in its configuration, so an actor's owner can protect their key from a greedy director. Today the budget counts what actors report (D39). Deferred at milestone 4's ask point G.
- [ ] **Checking the costs actors declare,** for their models and for the tools they bring. Today the director believes what an actor reports, as an act of trust (D39, D53). Deferred at milestone 6's ask point B.

## Engine

- [ ] **The cost of a cue that failed midway.** A cue that fails midway, such as on a tool that gave up or a model request that timed out, reports an unknown cost, even when every model it could use is free. Under a budget, the director then releases the seat, and a local seat uses up one of its two restarts. Counting what the models spent before the failure would keep it known (D7, D39). Found in milestone 6's recorded runs, once for each.
- [ ] **An actor that didn't end after its release.** In milestone 6's two-machine run, the coder on the second machine never saw the director's release, and kept running after the play stopped; the machine shut down before its state could be seen. A guess that fits: the actor follows its task over a stream with no read timeout (`engine/a2a_client.py`), and the director counts an open stream as contact (`director/casting.py`), so a connection that dies quietly goes unnoticed on both sides. A read timeout of a heartbeat's length, with a poll after it, would bound it. Confirm with a run before changing it.
- [ ] **A model entry's request timeout.** A request to an OpenAI-compatible server has its client's limit, 10 minutes, retried twice; a local model writing a long answer can need more. In milestone 6's local b run, a tester's cue failed after 30 minutes on it. A model entry could set its own (D11). Found in milestone 6's recorded runs.
- [ ] **Prompt caching for seats,** once measured: the director caches its instructions (D61); a seat with one short cue could pay more for a cache write than it saves. Deferred at milestone 6's ask point H.

## Director

- [ ] **Surviving a crash of the director's process.** A play's state lives in the director's process; a director that crashes loses its cues in flight and its own conversation (D33). Continuing a run that ended, from its stage and its log, is done (D60). Deferred at milestone 4's ask point A.
- [ ] **A global defaults file for directors**, such as `~/.zanni/director.yaml`, without sharing a play's tokens across plays (D34). Deferred at milestone 4's ask point B.
- [ ] **Custom director roles**, with their own instructions, beside `zanni:director` (D34).
- [ ] **Soft verifiers** (a model judging), and **verifiers run on one workstream** instead of the whole stage (D35). Deferred at milestone 4's ask point C.
- [ ] **Several local seats from one actor configuration**, such as `{ config: ./coder.yaml, count: 3 }`, with numbered names (D36). Deferred at milestone 4's ask point D.
- [ ] **Version ranges** in package references, and **a command to clean the package cache** (D37). Deferred at milestone 4's ask point E.
- [ ] **Telling someone a gate is waiting** (a webhook, an email), **per-person approvers**, and **a web page for gates** (D38). Deferred at milestone 4's ask point F.
- [ ] **Token budgets**, as an alternative to prices, for actors whose models have none (D7, D39).
- [ ] **The director's total input.** Since D49, a turn ends after each long wait, so each new turn sends the instructions and the summary again. Since D61 the instructions are cached: in milestone 6's recorded runs, the director's share of a run's cost fell from 25% with caching off to 10–12% with it on, for the same work. It still reads about 280k input tokens in one round of the software script; sending the summary once per round would cut that (D49, D61). Found in milestone 5's recorded runs.
- [ ] **A floor for a cue's deadline.** The director chooses each cue's deadline, and on a local model it chose 10 to 20 minutes for cues its local seats needed longer for, in milestone 6's local runs; a seat past its deadline is recast, and a local seat is restarted at most twice (D36). A play could set the shortest deadline, or the director could fit it to the seat's models. Found in milestone 6's recorded runs.
- [ ] **Workstreams that depend on each other.** Parallel coders each get a workspace filled when their cue starts, so a workstream that uses another's code can't run its tests in the same round of cues: in milestone 6's two-coders run, the `web` coder couldn't import `app/convert.py`. The script could order such workstreams, or stub the shared contract first (D54). Found in milestone 6's recorded runs.
- [ ] **Holding an approved plan fixed.** A `before_writes` gate holds its paths back until it is approved, and no longer: in two of milestone 6's recorded runs the director had `backlog/` changed after the plan gate was approved, so the owner approved a plan that then changed. A gate could keep the paths it approved closed until the next round (D62). Found in milestone 6's recorded runs.
- [ ] **The cost of an interrupted turn.** A director stopped by hand mid-turn never logs that turn's cost (D39). Found in milestone 4's recorded runs.
- [ ] **Limiting a cue's overshoot.** The actor checks its cue's budget after each model response, so one expensive response can spend several times a small cue budget. Estimating a request's cost before sending it would bound that (D39). Found in milestone 4's recorded runs.

## Stage

- [ ] **Isolated writes:** a branch per seat, merged by the director, for scripts whose seats must edit the same files at the same time. Today writes are shared, parallel seats get paths of their own for each cue, and nobody merges (D44, D54). Alessio's condition at milestone 6's ask point C: if seats keep needing the same files, branches and merges come back as a decision.
- [ ] **Content that isn't text,** such as images, on the stage. Today a backend lists such a file, and refuses to read it with `not-text` (D43). Deferred at milestone 5's ask point A.
- [ ] **A stage server's own checks,** as a sixth tool such as `stage_verify`, and **model judges** as verifiers (`kind: soft`) (D45, D47). Deferred at milestone 5's ask point C.
- [ ] **Direct access to a git stage:** a checkout per seat, pushing its own branch, with tokens per seat. `zanni.cast`'s `stage.direct` stays reserved for it. A workspace, a local copy of the stage sent back through the director at the end of each cue, covers coding engines (D52). Deferred again at milestone 6's ask point A, to after the first version.
- [ ] **Changes made on a stage server outside the play** don't appear in `changes`, since the director's record holds only the play's own writes (D47).

## Later milestones

- [ ] **Browser tests** for the software script: a browser verifier on a verifier seat, and a browser tool for the tester's exploring (D56). Milestone 7.
- [ ] **Direct questions between actors** mid-cue, through the director, if the review loops prove too slow (D59).
- [ ] **Capability names shared across roles, connector packages and risk tiers** for the tools actors bring: the Connectors milestone. Bindings in an actor's configuration are its smallest part (D53).

- [ ] **Actors behind NAT that can't reach the director**, such as a director on a laptop with actors elsewhere: a tunnel or a relay. Actors already connect outwards (D21), so only the director must be reachable.
- [ ] **Connectors** (vision, open question "Connectors"; roadmap, after the first version).
- [ ] **Actors offered online, hired by a director.** Where an actor runs is up to whoever runs it (D32); in time, a director may hire actors that other people offer online. This goes with the vision's "actors hosted by other people", out of scope for the first version. Raised by Alessio at milestone 3's ask point D.
- [ ] **A domain for Zanni**, and moving the casting extension's URI to it (D22).
