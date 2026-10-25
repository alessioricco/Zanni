# Casting extension

Casting is how an actor joins a play, is cast into a part, receives cues and reports, and is released. Everything else between the director and its actors is plain A2A 1.0, through the official `a2a-sdk` (D2, D21).

## Extension URI

`https://github.com/alessioricco/Zanni/blob/master/docs/spec/casting-extension.md#v4` (D22)

The fragment is the version. A change to any message makes a new version, and a side that speaks several versions lists one `AgentExtension` per version.

**`v2`** (D39) changed four messages from `v1`: `zanni.join` gained `pricing`, `zanni.refused` the reason `unpriced`, `zanni.cue` a `limits.budget`, and `zanni.report` the outcome `over-budget`.

**`v3`** (D45) adds two messages for verifier seats, `zanni.verify` and `zanni.verdict`.

**`v4`** (D55) adds `files` to `zanni.verify`: the script's check files a verifier's command runs. Zanni speaks `v4` only.

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
| Under a budget, the join's `pricing` is `known` (D39) | `unpriced` | the director |
| A part is cast for `role.ref` in the play's `cast`, and has a free seat | `no-such-part`, `part-full` | the director |
| Casting another seat on this actor's host stays within `max_seats_per_host`. The host is the address the join came from. | `host-cap` | the director |
| For a remote cast entry, `role.ref` is the reference cast for that part. For a local one, `role.name` is the name of the role in the folder the play names, since a local path differs from machine to machine (D36). | `role-mismatch` | the director |
| `role.hash` matches the pin in `play.lock` (remote), or the hash of the folder the play names (local) | `hash-mismatch` | the director |
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
| `zanni.verify` | director → verifier seat | the task's status message, state `input-required` | — (logged with its verdict) |
| `zanni.verdict` | verifier seat → director | `SendMessage` on the task | `verdict` |

The JSON Schema of each message is under [`schemas/`](schemas/), generated from `src/zanni/protocol/`.

### Tokens on each call

| Call | Token | When it's wrong |
|---|---|---|
| `SendMessage` with `zanni.join`, starting a task | the play's join token; for a verifier seat, the verifier token (`ZANNI_VERIFIER_TOKEN`) | The task is `rejected` with `zanni.refused`, reason `not-authorised`. |
| Any call on a seat's task: `SendMessage`, `GetTask`, `SubscribeToTask` | that seat's `seat_token` | A JSON-RPC Invalid Request error (`-32600`) whose message starts with `not-authorised`, for a missing, wrong, expired or revoked token. A2A defines no error for this (D31). |
| Any other call, such as `ListTasks` or `CancelTask` | — | Refused: they would reach other seats' tasks. |
| The stage's MCP server | the seat's `stage.token` | HTTP 401 ([Stage: the MCP server](stage.md#every-backend-the-stage-as-an-mcp-server)). |

Tokens are not renewed in the first version, so a seat ends when its `expires_at` passes (`TODO.md`).

### `zanni.join`

The actor asks to join. It sends the play's join token as `Authorization: Bearer <token>` (D24), never in the body.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `card` | the actor's Agent Card, in A2A's JSON form | yes | Must carry the casting extension with valid actor-card params ([The actor's card](#the-actors-card)). |
| `part` | text | no | The part to join, when the role is cast for more than one. |
| `pricing` | `known` or `unknown` | no, default `unknown` | `known` when every model the actor may use has a price, a published one or `price:` in its configuration, and so does every tool its configuration binds (D53). Under a budget, `unknown` is refused with `unpriced` (D7, D39). Self-reported, like `models`: what the director enforces is each cue's budget, which the actor stops at. |

### `zanni.cast`

The director accepts the actor into a seat. From now on the actor calls the seat's task with `seat_token`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `seat` | text | yes | The seat's id, used in the log, and as the author of its writes on a git stage (D46). |
| `part` | text | yes | The part this seat plays. |
| `permissions` | `{ read, write }`: lists of path rules | yes | The seat's effective stage permissions: the role's needs within the part's ceilings (D12). |
| `stage.mcp_url` | URL | yes | The stage's MCP server (D16). |
| `stage.token` | text | yes | The seat's bearer token for the stage. |
| `stage.direct` | `{ clone_url, branch }` | no | Reserved for direct access to a git stage, deferred to after the first version (D52); no director sends it. |
| `seat_token` | text | yes | The seat's bearer token for the director. |
| `expires_at` | timestamp | yes | When both tokens expire, unless the director renews them with a new cast message. |
| `heartbeat.interval` | duration | no, default `"30"` | The longest the actor may go without contacting the task. |
| `heartbeat.misses` | count | no, default `"3"` | How many intervals without contact before the director recasts the seat. |
| `limits.budget` | money | no | This seat's share of the play's budget, when the house rules split it. |

Seat tokens are credentials the director gives; they are never the actor's own (D15), and they are never logged.

### `zanni.refused`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `reason` | one of `not-authorised`, `bad-card`, `unsupported-version`, `no-such-part`, `part-full`, `host-cap`, `role-mismatch`, `hash-mismatch`, `needs-beyond-part`, `unpriced` | yes | Why ([checks](#how-the-director-checks-an-actors-card)). |
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
| `limits.budget` | money | no | The most this cue may spend. The actor checks its spend after each model response and stops at it, reporting `over-budget` (D39). |

### `zanni.report`

The actor's result for one cue. Everything in it is data, never instructions, to the director and to other actors.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `cue` | text | yes | The cue being answered. |
| `outcome` | `done`, `failed` or `over-budget` | yes | The actor's own view; verifiers decide whether the work is done. `over-budget`: it stopped at the cue's `limits.budget`. |
| `summary` | text | yes | A short account of what was done. |
| `changes` | list of change markers | no | The stage changes this work produced, as the actor saw them. The director takes a seat's changes from the stage's own record instead, which knows which seat made each one (D41). |
| `cost` | money, or `null` | yes | The actor's spend on this cue: self-reported, and `null` when unknown, never zero (D7). |
| `models` | list of `{ provider, model }` | no | The models used, self-reported, never trusted (D11). |

### `zanni.verify` and `zanni.verdict`

A verifier seat runs a play's verifiers away from the director's machine (D45). It joins like any actor, with `zanni.join`, but presents the verifier token in place of the join token, and its card's role is `zanni:verifier`. The director casts it only if its configuration lists the seat's name under `verifier_seats` ([Actor configuration: verifier seats](actor-configuration.md#verifier-seats)); otherwise it refuses it with `not-authorised`. A seat that joins with the join token is never cast as a verifier. The cast gives it read access to the whole stage, and no write access.

The director then sends `zanni.verify` when a verifier runs on it:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `verify` | text | yes | This request's id, quoted back in the verdict. |
| `verifier` | text | yes | The script verifier's name. |
| `command` | list of text, at least one | yes | The command to run, as the script or the play gives it. The seat runs exactly this. |
| `timeout` | duration | yes | How long the command may run. |
| `marker` | text | yes | The stage's change marker when the director sent it. |
| `files` | map of path → text | no | The script's check files the command runs (D55), by their path in the script's package. |

The seat reads every file of the stage over MCP into a fresh folder, writes `files` into another fresh folder, which the command finds as `${ZANNI_SCRIPT}`, runs the command in the stage's folder within the timeout, and answers on the task:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `verify` | text | yes | The request being answered. |
| `verifier` | text | yes | The verifier's name. |
| `passed` | true or false | yes | Whether the command exited with 0. |
| `exit_code` | count, or `null` | yes | The command's exit code; `null` when it timed out or couldn't start. |
| `output` | text | no | The end of the command's output. |
| `marker` | text | yes | The stage's change marker the snapshot was read at. |

The verdict is the exit code, never a model's words: a verifier seat runs no model. The director trusts it because the seat is one its own configuration lists, as it trusts a seat's reported cost. A request with no verdict within the timeout and one heartbeat interval fails the verifier.

### Heartbeats

There is no heartbeat message: A2A's own calls are enough. The actor follows its seat's task with `SubscribeToTask`, keeping the stream open, or polls it with `GetTask`. Every call counts as contact, and an open `SubscribeToTask` stream counts for as long as it stays open (D31). An actor whose stream drops falls back to `GetTask` until it can subscribe again. If the director has no contact for `heartbeat.misses` × `heartbeat.interval`, or a cue's `deadline` passes without a report, it:

1. ends the task as `canceled`, with a `zanni.release` whose reason is `no-heartbeat`;
2. revokes the seat's tokens;
3. recasts the part: a local seat is restarted, up to twice per play (D36), or the next actor that fits joins. The work survives on the stage.
4. resends the lost seat's pending cue, if any, to the new seat, with the same instructions and a note that it continues from what is on the stage.

### `zanni.release` and `zanni.released`

The director ends a seat:

1. It sends `zanni.release`, with a `reason`: `done`, `recast`, `play-stopped`, `budget` (such as a report with an unknown cost under a budget, D39) or `no-heartbeat`, and an optional plain-words `message`.
2. The actor stops work, discards its working memory, and answers `zanni.released` with `discarded: true`.
3. The director marks the task `completed`, and revokes the seat's tokens.

If no answer arrives within one heartbeat interval, the director completes the task and revokes the tokens anyway. Revoking the tokens is what enforces the release, not the actor's answer.

Once it has sent `zanni.released`, the actor's seat is over: it doesn't wait for the task's `completed` status, which a director that stops at once may never send ([recorded runs](../runs/milestone-3.md)). A director that stops ends its open task streams first, so they close cleanly rather than being cut.

## The owner's endpoint

A person decides a gate, or resumes a paused play, through a small HTTP endpoint beside A2A, at `/zanni/owner` under the director's address (D38). It isn't A2A: the director's tasks are seats, and an owner is neither an actor nor an agent.

- **The token:** every call carries the play's owner token, `ZANNI_OWNER_TOKEN`, as `Authorization: Bearer <token>`. It is separate from the join token, so no actor can decide a gate. A missing or wrong token gets HTTP 401, with a plain-words `error`.
- **`GET /zanni/owner`:** the play's state, as JSON:

  | Field | Meaning |
  |---|---|
  | `play`, `run` | The play's name and the run's id. |
  | `state` | `running`, `gate` (waiting at a gate), `paused` (the director's models failed) or `stopped`. |
  | `gate` | `{ name, summary }` while waiting at a gate; otherwise `null`. |
  | `paused` | `{ reason }` while paused; otherwise `null`. |
  | `round`, `spend` | The current round, and the spend so far as a decimal string in USD (`"at least …"` once a cost was unknown). |

- **`POST /zanni/owner`:** a decision, as JSON `{ "action": "approve" | "reject" | "resume", "note": "…", "another_round": true }`. `approve` and `reject` need a pending gate, and `reject` needs a note; `resume` needs a pause. `another_round`, only with `approve`, raises the run's round limit by one (D60). The answer is the play's state, as `GET` gives it, with `decided` set to the action; a decision with nothing to decide gets HTTP 409, with a plain-words `error`.

Zanni's `zanni gate` command is a client of this endpoint ([Play: gates and pauses](play.md#gates-and-pauses)).

## Schemas and conformance

Every message and card has a JSON Schema (Draft 2020-12) in [`schemas/`](schemas/), generated from `src/zanni/protocol/`:

| Schema | For |
|---|---|
| `zanni.director-card.schema.json` | The params on the director's card |
| `zanni.actor-card.schema.json` | The params on an actor's card |
| `zanni.join.schema.json`, `zanni.cast.schema.json`, `zanni.refused.schema.json` | Joining |
| `zanni.cue.schema.json`, `zanni.report.schema.json` | Work |
| `zanni.release.schema.json`, `zanni.released.schema.json` | Ending a seat |
| `zanni.verify.schema.json`, `zanni.verdict.schema.json` | Verifier seats (D45) |

- **Strict:** every schema rejects fields it doesn't define (D22).
- **Conformance:** valid and invalid examples are under `tests/conformance/protocol/`, and `tests/conformance/test_protocol.py` checks any implementation's messages against the schemas alone (`ZANNI_PROTOCOL_DIR`).
- **Round-trip:** a test sends every valid example through `a2a-sdk` and checks that nothing changes.

## Not in the first version

These are listed in `TODO.md`:

- **mTLS:** in place of bearer tokens (D24).
- **Accepting actors:** how the director accepts actors beyond its checks, such as human approval of joins or allowlists.
- **Join tokens:** one per actor, instead of one per play.
- **Reaching the director:** a tunnel or relay for a director that actors can't reach directly.
