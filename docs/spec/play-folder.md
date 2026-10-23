# Play folder

A play is a folder holding what the actors do together:

```
plays/habit-tracker/
  play.yaml     # the play file: cast, stage, script, house rules
  roles.lock    # each role resolved to a commit
  script.yaml   # acts and scenes: who hands off to whom, loops, stop rules
  stage/        # shared state
  log/          # who did what, verifier results, costs
```

Only `play.yaml` is specified so far.

## The play file

`zanni play.yaml` starts the director. A play file is recognised by having `cast`.

```yaml
name: habit-tracker
director: wss://director.example.com
stage: git@github.com:alessio/habit-tracker.git
script: ./script.yaml
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
| `director` | URL (`ws`, `wss`, `http`, `https`) | no | this machine | the actor's host | Where actors connect to join. Each host decides whether it trusts this address. |
| `stage` | git URL or path | yes | — | the stage | Where the shared state lives. |
| `script` | path | no | none | the director | The workflow. The director reads it and gives cues; actors never read it. |
| `cast` | map of seat name → cast entry | yes, at least one | — | the director | Who is in the play. |
| `house_rules` | house rules | no | no budget, no gates | the director | Limits set when the director starts. Nothing in a role, the script or an actor can loosen them. |

### Cast entry

A cast entry is either a role reference (shorthand for `{ role: … }`) or:

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `role` | role reference ([actor file](actor-file.md#role-references)) | yes | — | the director, at casting | The role for these seats. |
| `seats` | number (`2`) or range (`1-4`), at least 1 | no | `1` | the director | How many actors may hold this seat. For a range, the director decides how many it casts, within it. |
| `host` | text | no | any host | the director | `local` means the director starts these seats itself, on its own machine. |

### House rules

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `budget` | number, at least 0, in USD | no | none | the director | The most the whole play may spend. A seat whose cost is unknown counts as unsafe, not as free (D7). |
| `gates` | list of text | no | none | the director | Moments that need human approval, such as `plan` and `release`. |

## Draft

- **Stage:** whether it is a git repo with a branch per seat or a service with an API is an open question in the vision ("Stage").
- **Other files:** the formats of `roles.lock`, `script.yaml` and `log/` aren't specified yet.
- **More house rules:** seat caps per host, risk tiers and stop rules aren't specified yet.
