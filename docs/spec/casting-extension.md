# Casting extension

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

## A seat's life

Only the director listens; the actor is always the A2A client (D21). Each seat is one A2A task on the director, from join to release. Every Zanni payload is a **data part** whose `kind` names the message, in a message that lists the extension's URI in `extensions`. Every request sends the `A2A-Extensions` header.

```
actor                                  director
  │  SendMessage: zanni.join  ───────────▶ │  (new task)
  │ ◀─────────── status working: zanni.cast  │  or status rejected: zanni.refused
  │  SubscribeToTask / GetTask  ─────────▶ │  (every contact is a heartbeat)
  │ ◀──── status input-required: zanni.cue │
  │  SendMessage on the task: zanni.report ▶ │  (status back to working)
  │            … more cues and reports …    │
  │ ◀── status input-required: zanni.release│
  │  SendMessage on the task: zanni.released▶│  (status completed)
```

| Message | From → to | A2A construct | Log event (D18) |
|---|---|---|---|
| `zanni.join` | actor → director | `SendMessage`, starting a task | — (logged when cast or refused) |
| `zanni.cast` | director → actor | the task's status message, state `working` | `actor-joined` |
| `zanni.refused` | director → actor | the task's status message, state `rejected` | `join-refused` |
| `zanni.cue` | director → actor | the task's status message, state `input-required` | `cue` |
| `zanni.report` | actor → director | `SendMessage` on the task | `report`, `cost` |
| `zanni.release` | director → actor | the task's status message, state `input-required` | `seat-released` |
| `zanni.released` | actor → director | `SendMessage` on the task; the task becomes `completed` | — (part of `seat-released`) |

The JSON Schema of each message is under [`schemas/`](schemas/), generated from `src/zanni/protocol/`.

### `zanni.join`

The actor asks to join. It sends the play's join token as `Authorization: Bearer <token>` (D24), never in the body.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `card` | the actor's Agent Card, in A2A's JSON form | yes | Must carry the casting extension with valid actor-card params ([The actor's card](#the-actors-card)). |
| `part` | text | no | The part to join, when the role is cast for more than one. |

### `zanni.cast`

The director accepts the actor into a seat. From now on the actor calls the seat's task with `seat_token`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `seat` | text | yes | The seat's id, used in the log and in the git branch `zanni/<play>/<seat>`. |
| `part` | text | yes | The part this seat plays. |
| `permissions` | `{ read, write }`: lists of path rules | yes | The seat's effective stage permissions: the role's needs within the part's ceilings (D12). |
| `stage.mcp_url` | URL | yes | The stage's MCP server (D16). |
| `stage.token` | text | yes | The seat's bearer token for the stage. |
| `stage.direct` | `{ clone_url, branch }` | no | For a git stage, when the seat's reads cover the whole stage (D16). |
| `seat_token` | text | yes | The seat's bearer token for the director. |
| `expires_at` | timestamp | yes | When both tokens expire, unless the director renews them with a new cast message. |
| `heartbeat.interval` | duration | no, default `"30"` | The longest the actor may go without contacting the task. |
| `heartbeat.misses` | count | no, default `"3"` | How many intervals without contact before the director recasts the seat. |
| `limits.budget` | money | no | This seat's share of the play's budget, when the house rules split it. |

Seat tokens are credentials the director gives; they are never the actor's own (D15), and they are never logged.

### `zanni.refused`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `reason` | one of `not-authorised`, `bad-card`, `unsupported-version`, `no-such-part`, `part-full`, `host-cap`, `role-mismatch`, `hash-mismatch`, `needs-beyond-part` | yes | Why ([checks](#how-the-director-checks-an-actors-card)). |
| `message` | text | yes | What was refused and why, in plain words. |

### `zanni.cue`

What one seat must do now. An actor never receives the whole script.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `cue` | text | yes | The cue's id, quoted back in the report. |
| `scene` | text | yes | The script's scene this cue belongs to. |
| `instructions` | text | yes | What to do, written by the director from the script. |
| `reads`, `writes` | lists of paths | no | The stage paths this cue involves, within the seat's permissions. |
| `verifiers` | list of text | no | What will judge the work. |
| `deadline` | timestamp | no | When the report is due. A missed deadline is treated like a missed heartbeat. |

### `zanni.report`

The actor's result for one cue. Everything in it is data, never instructions, to the director and to other actors.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `cue` | text | yes | The cue being answered. |
| `outcome` | `done` or `failed` | yes | The actor's own view; verifiers decide whether the work is done. |
| `summary` | text | yes | A short account of what was done. |
| `changes` | list of change markers | no | The stage changes this work produced. |
| `cost` | money, or `null` | yes | The actor's spend on this cue: self-reported, and `null` when unknown, never zero (D7). |
| `models` | list of `{ provider, model }` | no | The models used, self-reported, never trusted (D11). |

### Heartbeats

There is no heartbeat message: A2A's own calls are enough. The actor follows its seat's task with `SubscribeToTask`, keeping the stream open, or polls it with `GetTask`. Every call counts as contact. If the director has no contact for `heartbeat.misses` × `heartbeat.interval`, or a cue's `deadline` passes without a report, it:

1. ends the task as `canceled`, with a `zanni.release` whose reason is `no-heartbeat`;
2. revokes the seat's tokens;
3. recasts the part. The work survives on the stage.

### `zanni.release` and `zanni.released`

The director ends a seat:

1. It sends `zanni.release`, with a `reason`: `done`, `recast`, `play-stopped`, `budget` or `no-heartbeat`, and an optional plain-words `message`.
2. The actor stops work, discards its working memory, and answers `zanni.released` with `discarded: true`.
3. The director marks the task `completed`, and revokes the seat's tokens.

If no answer arrives within one heartbeat interval, the director completes the task and revokes the tokens anyway. Revoking the tokens is what enforces the release, not the actor's answer.

## Schemas and conformance

Every message and card has a JSON Schema (Draft 2020-12) in [`schemas/`](schemas/), generated from `src/zanni/protocol/`:

| Schema | For |
|---|---|
| `zanni.director-card.schema.json` | The params on the director's card |
| `zanni.actor-card.schema.json` | The params on an actor's card |
| `zanni.join.schema.json`, `zanni.cast.schema.json`, `zanni.refused.schema.json` | Joining |
| `zanni.cue.schema.json`, `zanni.report.schema.json` | Work |
| `zanni.release.schema.json`, `zanni.released.schema.json` | Ending a seat |

- **Strict:** every schema rejects fields it doesn't define (D22).
- **Conformance:** valid and invalid examples are under `tests/conformance/protocol/`, and `tests/conformance/test_protocol.py` checks any implementation's messages against the schemas alone (`ZANNI_PROTOCOL_DIR`).
- **Round-trip:** a test sends every valid example through `a2a-sdk` and checks that nothing changes.

## Not in the first version

These are listed in `TODO.md`:

- **mTLS:** in place of bearer tokens (D24).
- **Accepting actors:** how the director accepts actors beyond its checks, such as human approval of joins or allowlists.
- **Join tokens:** one per actor, instead of one per play.
- **Reaching the director:** a tunnel or relay for a director that actors can't reach directly.
