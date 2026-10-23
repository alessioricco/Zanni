# To do

Things decided to come later. Each names where it was deferred. Remove an item when it is done, or when a decision replaces it.

## Security

- [ ] **mTLS between actors and the director.** The first version uses bearer tokens: a join token, then tokens scoped to each seat (D24). Replace or back them with mutual TLS, once there are certificates to manage. Deferred at casting ask point C ("make it work, then make it better").
- [ ] **How the director accepts an actor.** Today a valid join token and a role that fits a free part are enough (D21, D24). Decide whether joins need a human's approval, an allowlist of actors or roles, or a policy in the play's house rules. Deferred at casting ask point A.
- [ ] **One join token per actor.** The first version shares one join token per play (`ZANNI_JOIN_TOKEN`). Per-actor tokens would let a director revoke one actor without the rest.
- [ ] **The director's own configuration.** The director is an actor too. Decide whether `zanni play.yaml` reads the director's credentials (join tokens) from the environment, as now, or from a director configuration file.
- [ ] **Secrets management for actors on cloud services** (D15).

## Later milestones

- [ ] **Actors behind NAT that can't reach the director**, such as a director on a laptop with actors elsewhere: a tunnel or a relay. Actors already connect outwards (D21), so only the director must be reachable.
- [ ] **Connectors** (vision, open question "Connectors"; roadmap, after the first version).
- [ ] **A domain for Zanni**, and moving the casting extension's URI to it (D22).
