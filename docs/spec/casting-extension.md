# Casting extension

**Draft: being written (milestone 1, part 2).** The sections below are decided; the messages are still to come.

Casting is how an actor joins a play, is cast into a part, receives cues and reports, and is released. Everything else between the director and its actors is plain A2A 1.0, through the official `a2a-sdk` (D2, D21).

## Extension URI

`https://github.com/alessioricco/Zanni/blob/master/docs/spec/casting-extension.md#v1` (D22)

The fragment is the version. A change to any message makes a new version, and a side that speaks several versions lists one `AgentExtension` per version.

## Encoding

A2A carries extension params and data parts as protobuf `Struct` values, which have no integer type, so every number travels as a string (D23):

| Value | Encoding | Example |
|---|---|---|
| A count | decimal string, at least 0 | `"4"` |
| A duration | whole seconds, as a decimal string | `"30"` |
| Money | `{ amount, currency }`; `amount` is a plain decimal string, at least 0; `currency` is `USD` | `{ "amount": "20.10", "currency": "USD" }` |
| A range | `{ min, max }`, both counts, `min` ≤ `max` | `{ "min": "1", "max": "4" }` |
| A timestamp | RFC 3339, UTC | `"2026-10-24T09:30:00Z"` |
| An unknown cost | `null` (D7) | `null` |

The round-trip that led to this, through `a2a-sdk` 1.2.3's types:

| Sent | Arrived | |
|---|---|---|
| `4` | `4.0` | changed |
| `"4"` | `"4"` | exact |
| `9007199254740993` | `9007199254740992.0` | changed |
| `"9007199254740993"` | `"9007199254740993"` | exact |
| `{"min": 1, "max": 4}` | `{"min": 1.0, "max": 4.0}` | changed |
| `{"amount": "20.10", "currency": "USD"}` | the same | exact |

## The cards

Both sides describe themselves with an A2A Agent Card. A2A's own fields are used as A2A defines them. Only what A2A has no field for goes in the casting extension's `params` on `capabilities.extensions`, with `kind` saying which card it is.

### The director's card

The director is the only side that listens (D21). It serves its card at A2A's well-known path (`/.well-known/agent-card.json`).

| Card field | Holds |
|---|---|
| `name`, `description`, `version` | The director's own, as A2A defines them. |
| `skills` | One skill with `id: join`: actors join the play through it. |
| `security_schemes`, `security_requirements` | One HTTP bearer scheme: join and seat tokens (D24). |
| `capabilities.extensions` | The casting extension, `required: true`, with the params below. |

| Param | Type | Meaning |
|---|---|---|
| `kind` | `"zanni.director-card"` | |
| `play` | text | The play's `name`. |
| `script` | text | The play's `script` reference. |

### The actor's card

The actor never listens, so it doesn't serve a card: it sends its card inside its join message. It builds the card from its role package and its configuration.

| Card field | Holds |
|---|---|
| `name` | The actor configuration's `name`, or the role's `name`. |
| `description` | The role's `mission`. |
| `version` | The role's `version`. |
| `skills` | One per skill in the role package: `id` and `name` from the skill's `name`, and its `description`. |
| `capabilities.extensions` | The casting extension, with the params below. |

| Param | Type | Required | Meaning |
|---|---|---|---|
| `kind` | `"zanni.actor-card"` | yes | |
| `actor` | text | no | The configuration's `name`. |
| `role.ref` | package reference | yes | The reference the actor was started with. |
| `role.hash` | `sha256:` and 64 hex characters | yes | The role package's content hash, computed as for `play.lock` (D18). |
| `role.name`, `role.version` | text, `major.minor.patch` | yes | From `role.yaml`. |
| `role.needs` | `stage_read`, `stage_write`, `tools`: lists of text | no | From `role.yaml`. |
| `role.never` | list of text | no | From `role.yaml`. |
| `role.model_needs` | `tools` (true/false), `context` (text, such as `"32k"`), `tier` (text) | no | From `role.yaml`. Hints only (D11). |
| `models` | list of `{ provider, model }` | no | The models the actor says it runs. **Self-reported:** logged, never trusted, never checked (D11). |

### How the director checks an actor's card

When an actor asks to join, the director checks, in this order:

| Check | Refused with | Enforced by |
|---|---|---|
| The join token is valid (D24) | `not-authorised` | the director |
| A part is cast for `role.ref` in the play's `cast`, and has a free seat | `no-such-part`, `part-full` | the director |
| Casting another seat on this actor's host stays within `max_seats_per_host` | `host-cap` | the director |
| `role.ref` is the reference cast for that part | `role-mismatch` | the director |
| `role.hash` matches the pin in `play.lock`, when there is one | `hash-mismatch` | the director |
| Every `role.needs.stage_write` and `stage_read` rule is within the part's `writes` and `reads` ceilings, when the script sets them (D12) | `needs-beyond-part` | the director, at casting; the stage, on every operation |

- **Reference implementation:** `src/zanni/protocol/fit.py` implements the role, hash and ceiling checks as pure functions, so every director uses the same rules.
- **What the director can't check:** that the actor really runs the role it claims, or the models it lists. What it can enforce comes later: the stage holds every seat to its permissions, and verifiers judge the work.
