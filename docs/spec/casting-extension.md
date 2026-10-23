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
