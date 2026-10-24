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
- [ ] **Checking signed tags** when fetching packages. Deferred at milestone 4's ask point E (D37).
- [ ] **An actor's own spending cap**, in its configuration, so an actor's owner can protect their key from a greedy director. Today the budget counts what actors report (D39). Deferred at milestone 4's ask point G.

## Engine

- [ ] **Cap output tokens per request** in a model entry, so a small model stuck repeating itself stops early. A recorded `gemma3:4b` run looped for 280 s and 15,503 output tokens (docs/runs/milestone-2.md).

## Director

- [ ] **Surviving a restart of the director's process.** A play's state lives in the director's process; a director that stops loses the run (D33). Deferred at milestone 4's ask point A.
- [ ] **A global defaults file for directors**, such as `~/.zanni/director.yaml`, without sharing a play's tokens across plays (D34). Deferred at milestone 4's ask point B.
- [ ] **Custom director roles**, with their own instructions, beside `zanni:director` (D34).
- [ ] **Soft verifiers** (a model judging), and **verifiers run on one workstream** instead of the whole stage (D35). Deferred at milestone 4's ask point C.
- [ ] **Several local seats from one actor configuration**, such as `{ config: ./coder.yaml, count: 3 }`, with numbered names (D36). Deferred at milestone 4's ask point D.
- [ ] **Version ranges** in package references, and **a command to clean the package cache** (D37). Deferred at milestone 4's ask point E.
- [ ] **Telling someone a gate is waiting** (a webhook, an email), **per-person approvers**, and **a web page for gates** (D38). Deferred at milestone 4's ask point F.
- [ ] **Token budgets**, as an alternative to prices, for actors whose models have none (D7, D39).

## Later milestones

- [ ] **Actors behind NAT that can't reach the director**, such as a director on a laptop with actors elsewhere: a tunnel or a relay. Actors already connect outwards (D21), so only the director must be reachable.
- [ ] **Connectors** (vision, open question "Connectors"; roadmap, after the first version).
- [ ] **Actors offered online, hired by a director.** Where an actor runs is up to whoever runs it (D32); in time, a director may hire actors that other people offer online. This goes with the vision's "actors hosted by other people", out of scope for the first version. Raised by Alessio at milestone 3's ask point D.
- [ ] **`host-cap` at casting.** The director doesn't yet know an actor's host, so `max_seats_per_host` isn't enforced; it comes with the play's director (milestone 4).
- [ ] **A report's change markers with several seats.** An actor reports every change made on the stage while its cue ran. With one seat per stage that's exact; with several seats writing at once, a report could include another seat's changes. Fix with the play's director (milestone 4).
- [ ] **A domain for Zanni**, and moving the casting extension's URI to it (D22).
