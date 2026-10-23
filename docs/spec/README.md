# Zanni spec

**The spec is the product.** This repository is its reference implementation, and another implementation that passes the conformance tests (`tests/conformance/`) runs the same roles and plays.

The spec covers only what existing standards don't:

| Need | Standard | Zanni spec page |
|---|---|---|
| A role's character and instructions | `AGENTS.md` | — |
| A role's skills | SKILL.md | — |
| A role's tools | MCP, standard `mcp.json` | — |
| A role's Zanni fields | — | [Role package](role-package.md) |
| One actor instance: role, play, models, credentials | — | [Actor configuration](actor-configuration.md) |
| A production of a script: script, director, cast, stage, house rules | — | [Play](play.md) |
| Director to actor | A2A | — |
| Joining, seats, scoped credentials, release | A2A extension | [Casting extension](casting-extension.md) |

## Status

Version 0 is a draft, and anything may change until 1.0.

- **Normative:** each field table describes what the reference implementation validates today. The conformance tests check it.
- **Draft:** sections marked this way aren't decided. They link to the open question in the vision doc.

## Rules that apply to every Zanni file

- **Format:** YAML. Unknown keys are errors, and so are duplicate keys (D10).
- **No secrets in shared files:** in roles, scripts and plays, a key that looks like a secret (`key`, `token`, `secret`, `password`) is rejected at any depth. Only an actor configuration may hold credentials, under D15's safeguards.
- **Kinds:** the kind of file comes from its keys, never from its name or a flag (D9).
- **Errors:** an implementation reports each problem with the file, the line, the field path, what is wrong and what to change.
- **Enforcement:** every field that sets a permission or a limit names the component that enforces it: the stage, the director, a verifier or the actor (through its configuration). No limit relies on an actor obeying it.
