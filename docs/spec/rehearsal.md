# Rehearsal

A rehearsal runs one actor with no director: its cues come from a file, and its stage is a local folder (D26). It is how a role is tried out and tested before it joins a play, and a role package can ship rehearsals as its own tests, in `rehearsals/`.

```yaml
# examples/roles/slug-tester/rehearsals/smoke.yaml
rehearsal: smoke
description: The tester turns two acceptance criteria into passing pytest tests.
stage: ./smoke-stage
cues:
  - scene: Specify
    instructions: >-
      Read backlog/round-1.md and spec/slug.md. Write one pytest test for each acceptance criterion
      into tests/test_slug.py. The code under test is app.slug.slugify; import it as `from app.slug import slugify`.
    reads: [backlog/round-1.md, spec/slug.md]
    writes: [tests/test_slug.py]
    verifiers: [both tests run under pytest and pass]
verify:
  - name: tests-pass
    command: [uv, run, --no-project, --with, pytest, python, -m, pytest, -q, tests]
```

It is recognised by having `cues`.

## Running a rehearsal

A rehearsal never names an actor configuration, because configurations are private to the machine that runs them. Instead, an actor configuration points its `play` at the rehearsal:

```yaml
# examples/slug-tester.yaml
name: slug-tester-1
role: ./roles/slug-tester
play: ./roles/slug-tester/rehearsals/smoke.yaml
models:
  - { provider: ollama, model: qwen3.8:27b, base_url: "${OLLAMA_BASE_URL}" }
```

`zanni slug-tester.yaml` then:

1. **Copies the stage:** copies the rehearsal's `stage` folder to a fresh run folder, `<state_dir>/rehearsals/<rehearsal>/<run-id>/stage`. The role package is never written to.
2. **Sets permissions:** gives the actor the seat permissions its role asks for (`needs.stage_read`, `needs.stage_write`), enforced by the stage (D12).
3. **Runs the cues:** runs the actor on each cue in order, as if a director had sent it (`zanni.cue`), and prints each `zanni.report`.
4. **Verifies:** runs each `verify` command in the stage copy, and prints whether it passed.
5. **Logs:** appends every event to `<state_dir>/rehearsals/<rehearsal>/<run-id>/log.jsonl`, in the play log's format (D18): `run-started`, `cue`, `report`, `cost`, `verdict`, `run-stopped`.

`zanni rehearsal.yaml`, on its own, validates the rehearsal and runs nothing.

## Fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `rehearsal` | name | yes | — | — | The rehearsal's name, used in the run folder and the log. |
| `description` | text | no | none | — | What the rehearsal shows. |
| `stage` | folder path, relative to this file | yes | — | the stage | The starting state, copied fresh for every run. |
| `cues` | list of cues, at least one | yes | — | the rehearsal runner | What the actor is asked to do, in order. |
| `verify` | list of checks | no | none | the rehearsal runner | Commands run in the stage copy after the cues. |

### A cue

| Field | Type | Required | Meaning |
|---|---|---|---|
| `scene` | text | yes | A label for the cue, as in a script's scene. |
| `instructions` | text | yes | What to do. |
| `reads`, `writes` | lists of paths | no | The stage paths this cue involves. They are guidance for the actor; the role's needs are the permissions. |
| `verifiers` | list of text | no | What will judge the work, for the actor. |

### A check

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | name | yes | The check's name in the output and the log. |
| `command` | list of text, at least one | yes | The program and its arguments, run in the stage copy. The check passes when it exits with 0. |

**Not in the first version:** sandboxing `verify` commands. They run on the actor's machine with the user's permissions, so run rehearsals only from roles you trust, as with any role (see `TODO.md`).
