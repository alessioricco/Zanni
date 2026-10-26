# Play

A play is one production of a [script](script.md). It names the script it performs, the director, a role cast into each of the script's parts, the stage, and the house rules (D13). Two plays can perform the same script with different companies.

A play's folder holds:

```
plays/city-desk/
  play.yaml       # the play file
  director.yaml   # the director's own configuration: its models and credentials (D34)
  play.lock       # each package the play uses, pinned
  log/            # what happened: cues, results, verdicts, costs
```

## The play file

`zanni play.yaml` starts the director, which runs the play's script ([Running a play](#running-a-play)). A play file is recognised by having `cast`.

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
| `director` | `http` or `https` URL | no | this machine | the actor | Where actors connect to join: the director's A2A address, where its card is served (D30). Each actor decides whether it trusts this address. |
| `stage` | git URL, folder path, or `{ backend, … }` ([stage](stage.md#in-the-play-file)) | yes | — | the director | The play's workspace, and the backend that stores it: `folder`, `git` or `mcp`. The director enforces each seat's permissions above every backend (D43). |
| `cast` | map of part name → cast entry | yes, at least one | — | the director | A role for each of the script's parts. |
| `house_rules` | house rules | no | no limits | the director | Limits set when the director starts. Nothing in a role, the script or an actor can loosen them. |
| `verifiers` | map of a script verifier's name → `{ command, timeout, runs_on }` | no | the script's commands, on the director | the director | This play's commands for its script's verifiers, and where each runs ([below](#verifiers)). |

### Cast entry

A cast entry is either a package reference (shorthand for `{ role: … }`) or:

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `role` | package reference | yes | — | the director, at casting | The role cast into this part. |
| `seats` | number (`2`) or range (`1-4`), at least 1 | no | the part's seats in the script | the director | How many actors hold this part. It must be within the script's seats for the part. For a range, the director decides how many to cast, within it. |
| `host` | text | no | any host | the director | `local` means the director starts these seats itself, on its own machine, from the actor configurations its director configuration lists (D36). |

### House rules

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `budget` | number, at least 0, in USD | no | none | the director | The most the whole play may spend. A seat whose cost is unknown counts as unsafe, not as free (D7). |
| `gates` | list of names | no | none | the director | Which of the script's gates this play enforces, such as `plan` and `release`. Each must be one of the script's `gates`. |
| `max_seats_per_host` | whole number, at least 1 | no | no cap | the director | The most seats the director casts onto one machine, because actors on one machine share its GPU. A machine is told by the address its actors join from. |
| `gate_timeout` | duration: whole seconds, or a number with `s`, `m` or `h`, such as `30m` | no | none: a gate waits | the director | How long a gate, or a pause, may wait for a person. When it passes, the run stops with reason `gate` (or `paused`) (D38). |
| `max_rounds` | whole number, at least 1 | no | the script's `stop.max_rounds` | the director | The most rounds one run of this play may take: at most the script's, when it sets one. The owner may grant one more at a gate, and a run that [continues](#continuing-a-play) another counts its own rounds (D60). |
| `max_director_turns` | whole number, at least 1 | no | `30` | the director | The most model turns the director takes in one round. When it is reached, the round ends; if the round's work isn't verified, the run stops with reason `director-turns` (D33). |
| `requests_per_turn` | whole number, at least 1 | no | `25` | the director | The most model requests in one director turn (D49). |
| `cast_timeout` | duration, as `gate_timeout` | no | `10m` | the director | How long a part below its minimum seats, with no local seat left to start, waits for an actor to join, at the start or after losing a seat; and how long the start waits for each verifier seat a verifier `runs_on`. When it passes, the run stops with reason `uncastable` (D50). |

**Not in the first version:** risk tiers (read, spend, external action, irreversible). The vision keeps high-risk scripts out of the first version.

### Verifiers

A script names its verifiers and what each checks; only the play knows its project's commands, such as `pytest` or `npm test` (D35).

```yaml
verifiers:
  tests-pass: { command: [npm, test], timeout: 600, runs_on: ci-box }
```

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `command` | list of text, at least one | no | the script's | The command to run. |
| `timeout` | whole seconds, at least 1 | no | the script's | How long it may run before it fails. |
| `runs_on` | a verifier seat's name | no | the director | Where it runs: a verifier seat listed in the director's configuration ([Actor configuration: verifier seats](actor-configuration.md#verifier-seats)) (D45). |

- **Only the script's names:** a play gives commands for its script's verifiers; it can't add or remove one.
- **Every verifier needs a command:** the play's, or else the script's default. One with neither is refused before anything runs.
- **A snapshot:** every verifier runs on a snapshot of the stage, a fresh folder, never on the stage itself (D45).
- **`runs_on`:** a name the director's configuration doesn't list stops the play before it starts. The verdict comes from the verifier seat's exit code, and the log names the seat that ran it.

## Checking a play against its script

When the play's script is local, `zanni play.yaml` loads it and checks the play against it:

- every part in `cast` is one of the script's parts, with a "did you mean" for near misses;
- every part the script doesn't mark `optional` is cast;
- every `seats` is within the script's seats for that part;
- every gate in `house_rules.gates` is one of the script's gates;
- `house_rules.max_rounds` is at most the script's `stop.max_rounds`, when the script sets one;
- every name in `verifiers` is one of the script's verifiers, and every script verifier has a command.

Problems are reported on the play file's lines. A missing or invalid script is reported too: on the play's `script:` line if the path doesn't exist, or on the script's own lines if the script itself is invalid.

`zanni --check` then lists every verifier command the director will run, and whether it comes from the script or the play, because they run with the user's permissions.

When the script is remote (`host/owner/name@version`), these checks need it fetched. `zanni --check` says so, and the director runs them when it fetches the script, before anything starts.

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

**When it is written:** the director writes `play.lock` the first time it resolves the play's packages. A run never rewrites an existing `play.lock`; only `zanni play.yaml --update` does, re-resolving every tag and printing what changed: the commits, and the verifier commands that changed (D37).

**When it is checked:**

- **By the director:** a pinned commit already fetched is used without touching the network. Otherwise the director fetches the pinned tag, and refuses to start if it now points to another commit (naming both) or if the package's hash doesn't match its pin.
- **Local packages:** a local folder is pinned by its hash only. If it changed since `play.lock` was written, the director says so and uses its current hash; `--update` re-pins it.
- **By `zanni --check`:** if `play.lock` exists, `zanni` checks that every remote package the play uses is pinned in it.

## Running a play

`zanni play.yaml`, or `zanni director.yaml` for the play its director configuration names, runs the play on this machine (D33–D38):

1. **The director's configuration:** from `--director <file>`, or else `director.yaml` beside the play file ([Actor configuration: a director's configuration](actor-configuration.md#a-directors-configuration)). Its models must all be priced when the play has a budget.
2. **The packages:** the script and every role are resolved, fetched when remote, and checked against `play.lock`, which is written when missing ([The lockfile](#the-lockfile)).
3. **The checks:** the play is checked against its script, as `--check` does.
4. **The stage:** a folder stage must exist; a git stage is cloned into the run's folder, on a new branch (D46); an `mcp` stage's server must answer with the director's token (D47). Then the stage must hold the script's `stage.expects`. A run that [continues](#continuing-a-play) another starts from where that one left the stage.
5. **Serving:** the director serves its A2A card and its stage's MCP server on one address (`--listen host:port`, default `127.0.0.1` on a free port), and writes `log/director.json` with that address and the run's id, never a token, so `zanni gate` can find it. It removes the file when the run ends.
6. **Casting:** it starts the local seats and local verifier seats its configuration lists, and accepts actors joining with the join token, and remote verifier seats with the verifier token. Before its first turn, every part has at least its minimum seats, and every verifier seat a verifier `runs_on` has joined, within `cast_timeout`. A local seat the director released can be started again by a later `cast`. A local seat refused at join isn't restarted (D50).
7. **The script:** the director's turns follow the script, through its tools ([Script: how the director follows a script](script.md#how-the-director-follows-a-script)).
8. **The end:** every seat is released, local seats are stopped, and the command exits with:
   - 0 when the director stopped the play as `done`, and the rules accepted it;
   - 1 when it ran and stopped for any other reason: a failed verifier, the budget, a rejected or unanswered gate, an unanswered pause, the turn cap, the round cap, a part that couldn't be cast, or the director's own reason;
   - 2 when it couldn't start: a file problem, a package that can't be fetched or doesn't match `play.lock`, a missing director configuration, an unpriced director under a budget, a stage that can't be reached or cloned, a verifier seat the director's configuration doesn't list, or a `--continue` run id the play's log doesn't have.

   A git stage's run branch is pushed as its `push` setting says ([Stage: pushing](stage.md#pushing)).

### Gates and pauses

- **A gate pauses the play.** At a gate in `house_rules.gates`, the director logs `gate-pending` with a summary (the scene, the files changed since the last gate, the verdicts) and sends no new cue until a person decides. Seats stay cast, and keep their heartbeats. A gate the play doesn't list is skipped, and logged as skipped.
- **A pause:** when every one of the director's own models fails, or an `mcp` stage stays unreachable (D47), the play pauses the same way, until the owner resumes it (D33).
- **Deciding:** with `zanni gate <play file or director URL> approve | reject | resume`, from any machine that can reach the director, with the play's owner token ([Casting extension: the owner's endpoint](casting-extension.md#the-owners-endpoint)). On a rejection, the director gets the note, and may revise or stop.
- **Another round:** `zanni gate <play> approve --another-round --note "…"` approves the gate and raises the run's round limit by one (D60). Only the owner, who sets the house rules, can extend them. The note reaches the director as the owner's input for the next round. The budget is unchanged.
- **`gate_timeout`:** stops the run when a gate or a pause has waited that long.

### Continuing a play

`zanni play.yaml --continue <run-id>` starts a new run from where an earlier run of the same play left off (D60):

- **The stage:** a git stage's new run branch starts from the earlier run's branch, `zanni/<play>/<run-id>`, from the earlier run's folder, or else from the remote, instead of `branch`. A folder stage already holds its files, and an `mcp` stage is as its server holds it.
- **The round:** the count continues from the earlier run's last round, read from its log, so a play that ended in round 1 continues with round 2. The round limit counts the new run's own rounds.
- **A new run:** with its own run id, budget, cast and log. Its `run-started` event names the run it continues.
- **What isn't restored:** cues in flight and the director's own conversation. The new director reads the stage, and its state summary says which run it continues.
- **Refused:** a run id the play's `log/` doesn't have, or a git stage branch that is in neither the run's folder nor the remote, is exit 2, with what to change.

### The budget

The play's spend is every report's cost plus the director's own (D39):

- **Before casting:** under a budget, an actor whose models aren't all priced is refused (`unpriced`).
- **Per cue:** each cue carries a budget, by default the budget not yet reserved divided among the seats with no pending cue. A pending cue reserves it; its report replaces the reservation with the actual cost. The actor stops at its cue's budget and reports `over-budget`.
- **Unknown cost:** a report with an unknown cost under a budget releases that seat (reason `budget`) and recasts its part; the spend is then shown as "at least" that much.
- **The director's own spend:** counted after each of its model responses, before that response's tool calls run, so cue budgets see it at once. A turn whose models all fail still counts what it spent before failing.
- **Stopping:** the run stops with reason `budget` when nothing is left to reserve, or once the spend reaches the budget, even in the middle of a director turn. One model call can overshoot it.
- **What it can't enforce:** costs are what actors report. The real cap on a key is its owner's, such as a provider's spending limit.

## The log

`log/` holds one file per run of the play, `log/<run-id>.jsonl`. Each line is one JSON object, and lines are only ever appended. Every object has:

- `ts`: when it happened, as RFC 3339 UTC;
- `run`: the run's id;
- `event`: one of the types below;
- that event type's fields.

| `event` | Fields | When |
|---|---|---|
| `run-started` | `play`, `script` (reference and commit), `continues` (a run id, or `null`), `round` (the first round's number) | The director starts the run (D60). |
| `seat-started`, `seat-exited` | `seat` (its configuration's `name`), `part`, and `exit_code` when it exits | The director starts or sees the end of a local seat's process (D36). |
| `seat-not-restarted` | `seat`, `reason` | A local seat that ended isn't restarted: it was refused at join, or was restarted twice already (D36, D50). |
| `verifier-joined` | `seat`, `actor` | A verifier seat joins (D45). |
| `push` | `branch`, `ok`, `detail` | The director pushes a git stage's run branch, or fails to (D46). |
| `stage-unavailable` | `detail` | An `mcp` stage stopped answering (D47). |
| `actor-joined` | `seat`, `part`, `role`, `actor` (its configuration's `name`) | An actor is cast into a seat. |
| `join-refused` | `reason`, `actor`, `role` | The director refuses an actor (D24). |
| `cue` | `seat`, `scene`, `cue`, `budget`, `deadline` | The director gives a cue. A resent cue has a new `deadline` (D36). |
| `report` | `seat`, `scene`, `outcome`, `summary`, `changes` and `refused` (from the stage's record, D41, D52) | An actor reports back. `refused` lists the operations the permission layer refused during the cue. |
| `verdict` | `scene`, `verifier`, `kind` (`hard` or `soft`), `passed`, `detail`, `source` (`script` or `play`), `marker` (the stage's change marker it ran against), `by` (`director`, or the verifier seat) | A verifier runs (D45). |
| `gate-pending` | `gate`, `summary` | The play waits at a gate. |
| `gate` | `gate`, `decision` (`approved`, `rejected` or `skipped`), `by`, `note`, `another_round` | A human decides a gate, or the play doesn't enforce it. `another_round` is true when the owner granted one more round (D60). |
| `paused`, `resumed` | `reason`; `by` and `note` when resumed | Every one of the director's models failed; the owner resumed it (D33). |
| `cost` | `seat` (or `director`), `model`, `amount` (decimal string in USD, or `null` if unknown); for the director, `input_tokens` and `output_tokens` | A seat reports its spend, or the director counts one of its turns. |
| `fallback` | `seat`, `model`, `reason`, `detail` | A model failed and the actor moved to its next one, or stopped (D27, D28). |
| `tool-refused` | `tool`, `reason` | The rules refused one of the director's tool calls (D33). |
| `round-ended` | `round`, `reason` | A round ends. |
| `seat-released` | `seat`, `reason` | The director ends a seat. |
| `run-stopped` | `reason` (`done`, `budget`, `gate`, `paused`, `director-turns`, `max-rounds`, `uncastable`, or the director's own), `completed`, `round` (the round it ended in) | The run ends. |

- **No credentials:** an actor's credentials never appear in the log (D15).
- **Actor text is data:** text an actor wrote, such as a report's `summary`, is logged as data.
- **Not validated:** `zanni` doesn't validate log files.
