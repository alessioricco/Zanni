# Play

A play is one production of a script: the director, a role cast into each of the script's parts, the stage, and the house rules. The script is the reusable work and lives elsewhere, published like a role (D13). A play's folder holds:

```
plays/habit-tracker/
  play.yaml     # the play file: script, director, stage, cast, house rules
  roles.lock    # each role and the script resolved to a commit
  log/          # who did what, verifier results, costs
```

Only `play.yaml` is specified so far.

## The play file

`zanni play.yaml` starts the director, which runs the play's script. A play file is recognised by having `cast`.

```yaml
name: habit-tracker
script: github.com/someone/habit-tracker@1.0.0
director: wss://director.example.com
stage: git@github.com:alessio/habit-tracker.git
cast:
  product-owner: github.com/zanni-roles/product-owner@1.0.0
  tester: github.com/someone/tester@1.4.0
  coder: { role: github.com/zanni-roles/coder@1.0.0, seats: 1-4, host: local }
house_rules:
  budget: 20.00
  gates: [plan, release]
```

### Fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `name` | text | yes | — | the director | The play's name, used in the log and in summaries. |
| `director` | URL (`ws`, `wss`, `http`, `https`) | no | this machine | the actor | Where actors connect to join. Each actor decides whether it trusts this address. |
| `stage` | git URL or path | yes | — | the stage | Where the shared state lives. |
| `script` | package reference ([references](actor-configuration.md#package-references)) | yes | — | the director | The script this play performs. The director reads it and gives cues; actors never read it. |
| `cast` | map of part name → cast entry | yes, at least one | — | the director | A role for each of the script's parts. |
| `house_rules` | house rules | no | no budget, no gates | the director | Limits set when the director starts. Nothing in a role, the script or an actor can loosen them. |

### Cast entry

A cast entry is either a role reference (shorthand for `{ role: … }`) or:

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `role` | package reference | yes | — | the director, at casting | The role cast into this part. |
| `seats` | number (`2`) or range (`1-4`), at least 1 | no | `1` | the director | How many actors may hold this seat. For a range, the director decides how many it casts, within it. |
| `host` | text | no | any host | the director | `local` means the director starts these seats itself, on its own machine. |

### House rules

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `budget` | number, at least 0, in USD | no | none | the director | The most the whole play may spend. A seat whose cost is unknown counts as unsafe, not as free (D7). |
| `gates` | list of text | no | none | the director | Moments that need human approval, such as `plan` and `release`. |

## Draft

- **Stage:** whether it is a git repo with a branch per seat or a service with an API is an open question in the vision ("Stage").
- **Other files:** the formats of the lockfile and `log/` aren't specified yet.
- **Checking a play against its script:** that every part is cast and seats are within the script's limits.
- **More house rules:** seat caps per host, risk tiers and stop rules aren't specified yet.
