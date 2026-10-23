# Play

A play is one production of a [script](script.md). It names the script it performs, the director, a role cast into each of the script's parts, the stage, and the house rules (D13). Two plays can perform the same script with different companies.

A play's folder holds:

```
plays/city-desk/
  play.yaml     # the play file
  play.lock     # each remote package the play uses, pinned to a commit
  log/          # what happened: cues, results, verdicts, costs
```

## The play file

`zanni play.yaml` starts the director, which runs the play's script. A play file is recognised by having `cast`.

```yaml
# examples/plays/newsroom/play.yaml
name: city-desk
script: ../../scripts/newsroom
stage: ./stage
cast:
  editor: github.com/zanni-roles/editor@0.1.0
  reporter: { role: github.com/zanni-roles/reporter@0.1.0, seats: 2 }
  fact-checker: github.com/zanni-roles/fact-checker@0.1.0
house_rules:
  budget: 5.00
  gates: [publish]
  max_seats_per_host: 2
```

### Fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `name` | text | yes | — | the director | The play's name, used in the log and in summaries. |
| `script` | package reference ([references](actor-configuration.md#package-references)) | yes | — | the director | The script this play performs. A local path may point to `SCRIPT.md` or to its folder, relative to the play file. |
| `director` | URL (`ws`, `wss`, `http`, `https`) | no | this machine | the actor | Where actors connect to join. Each actor decides whether it trusts this address. |
| `stage` | git URL, folder path, or `{ backend, … }` ([stage](stage.md#in-the-play-file)) | yes | — | the stage | The play's workspace, and the backend that stores it and enforces each seat's permissions. |
| `cast` | map of part name → cast entry | yes, at least one | — | the director | A role for each of the script's parts. |
| `house_rules` | house rules | no | no limits | the director | Limits set when the director starts. Nothing in a role, the script or an actor can loosen them. |

### Cast entry

A cast entry is either a package reference (shorthand for `{ role: … }`) or:

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `role` | package reference | yes | — | the director, at casting | The role cast into this part. |
| `seats` | number (`2`) or range (`1-4`), at least 1 | no | the part's seats in the script | the director | How many actors hold this part. It must be within the script's seats for the part. For a range, the director decides how many to cast, within it. |
| `host` | text | no | any host | the director | `local` means the director starts these seats itself, on its own machine. |

### House rules

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `budget` | number, at least 0, in USD | no | none | the director | The most the whole play may spend. A seat whose cost is unknown counts as unsafe, not as free (D7). |
| `gates` | list of names | no | none | the director | Which of the script's gates this play enforces, such as `plan` and `release`. Each must be one of the script's `gates`. |
| `max_seats_per_host` | whole number, at least 1 | no | no cap | the director | The most seats the director casts onto one machine, because actors on one machine share its GPU. |

**Not in the first version:** risk tiers (read, spend, external action, irreversible). The vision keeps high-risk scripts out of the first version.

## Checking a play against its script

When the play's script is local, `zanni play.yaml` loads it and checks the play against it:

- every part in `cast` is one of the script's parts, with a "did you mean" for near misses;
- every part the script doesn't mark `optional` is cast;
- every `seats` is within the script's seats for that part;
- every gate in `house_rules.gates` is one of the script's gates.

Problems are reported on the play file's lines. A missing or invalid script is reported too: on the play's `script:` line if the path doesn't exist, or on the script's own lines if the script itself is invalid.

When the script is remote (`host/owner/name@version`), these checks need it fetched. `zanni` says so in its output, and the director runs the checks when it fetches the script (milestone 4).

## The lockfile

`play.lock` sits next to the play file. It pins every package the play uses: its script, and the role cast into each part.

```yaml
lock_version: 1
script:
  github.com/someone/habit-tracker@1.0.0: { commit: 0123456789abcdef0123456789abcdef01234567, hash: "sha256:…" }
roles:
  github.com/someone/tester@1.4.0: { commit: 89abcdef0123456789abcdef0123456789abcdef, hash: "sha256:…" }
  roles/coder: { hash: "sha256:…" }
```

It is recognised by having `lock_version`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `lock_version` | `1` | yes | The format's version. |
| `script` | map with exactly one reference → pin | yes | The script the play performs. |
| `roles` | map of reference → pin | no | Every role in the cast. |
| pin `commit` | 40 lowercase hex characters | for remote references | The commit the reference resolved to. |
| pin `hash` | `sha256:` and 64 lowercase hex characters | yes | The package's content hash. |

**The content hash** is the SHA-256 of a text listing every file in the package, excluding `.git/`. The text has one line per file, sorted by path. Each line is the file's own SHA-256 in hex, two spaces, and its path relative to the package root with `/` separators, then a newline (the format of `sha256sum`).

**When it is written:** the director writes `play.lock` the first time it resolves the play's packages, and only rewrites it when asked to update (milestone 4).

**When it is checked:**

- **By the director:** when it fetches a package, the package's hash must match its pin, or the director refuses to start.
- **By `zanni play.yaml`:** if `play.lock` exists, `zanni` checks that every remote package the play uses is pinned in it.

## The log

`log/` holds one file per run of the play, `log/<run-id>.jsonl`. Each line is one JSON object, and lines are only ever appended. Every object has:

- `ts`: when it happened, as RFC 3339 UTC;
- `run`: the run's id;
- `event`: one of the types below;
- that event type's fields.

| `event` | Fields | When |
|---|---|---|
| `run-started` | `play`, `script` (reference and commit) | The director starts the run. |
| `actor-joined` | `seat`, `part`, `role`, `actor` (its configuration's `name`) | An actor is cast into a seat. |
| `cue` | `seat`, `scene`, `cue` | The director gives a cue. |
| `report` | `seat`, `scene`, `summary`, `changes` (stage change markers) | An actor reports back. |
| `verdict` | `scene`, `verifier`, `kind` (`hard` or `soft`), `passed`, `detail` | A verifier runs. |
| `gate` | `gate`, `decision` (`approved` or `rejected`), `by` | A human decides a gate. |
| `cost` | `seat`, `model`, `amount` (decimal string in USD, or `null` if unknown) | A seat reports its spend. |
| `seat-released` | `seat`, `reason` | The director ends a seat. |
| `run-stopped` | `reason` (the stop rule, a gate, the budget, or a person) | The run ends. |

- **No credentials:** an actor's credentials never appear in the log (D15).
- **Actor text is data:** text an actor wrote, such as a report's `summary`, is logged as data.
- **Not validated:** `zanni` doesn't validate log files.
