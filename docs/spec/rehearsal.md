# Rehearsal

A rehearsal runs one actor on cues from a file, against a copy of a local folder, with no play file or script (D26). A director is started for it, so the actor works over the same wire as in a play (D29). It is how a role is tried out and tested before it joins a play, and a role package can ship rehearsals as its own tests, in `rehearsals/`.

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
2. **Starts a director:** in the same process, on `127.0.0.1`, with a join token made up for the run. Its one part is the actor's role, and the part's ceilings are the role's needs (`needs.stage_read`, `needs.stage_write`). The director enforces them on every stage operation (D43).
3. **Joins it:** the actor joins over A2A, exactly as it would join a remote director, and reaches the stage through the director's MCP server.
4. **Runs the cues:** the director sends each cue in order as a `zanni.cue`; the actor answers each with a `zanni.report`, which is printed.
5. **Releases the seat:** after the last report.
6. **Verifies:** runs each `verify` command in the stage copy, and prints whether it passed.
7. **Logs:** two logs go in the run folder:
   - `log.jsonl`, the director's, in the play log's format (D18): `run-started`, `actor-joined`, `cue`, `report`, `cost`, `seat-released`, `verdict`, `run-stopped`;
   - `actor-log.jsonl`, the actor's own ([The actor's log](actor-configuration.md#the-actors-log)).

`zanni rehearsal.yaml`, on its own, validates the rehearsal and runs nothing.

## Serving a rehearsal

`zanni rehearsal.yaml --serve` serves the rehearsal to an actor anywhere: on this machine, or on another that can reach it (D29).

```
$ export ZANNI_JOIN_TOKEN=…        # the same value goes in the actor's credentials
$ zanni examples/roles/slug-tester/rehearsals/smoke.yaml --serve --listen 0.0.0.0:8765
Serving rehearsal 'smoke' for the role slug-tester at http://0.0.0.0:8765; waiting for an actor
```

- **Its role:** the rehearsal must be in a role package's `rehearsals/` folder. That role is the one part, with one seat, and its needs are the part's ceilings.
- **Which actors fit:** an actor fits if it plays a role of that name (otherwise `role-mismatch`), with the same content hash as the package (otherwise `hash-mismatch`), and joins with the token in `ZANNI_JOIN_TOKEN`, which is required.
- **The address:** `--listen host:port` sets where the director listens. The default is `127.0.0.1` on a free port. The address actors use is printed.
- **Joining:** the actor's configuration points its `play` at that address.
- **The run:** the director copies the stage to `~/.zanni/rehearsals/<rehearsal>/<run-id>/`, sends the cues to the first actor that fits, and releases its seat. It then runs `verify` and exits with the codes of [D28](#exit-codes).
- **Losing the actor:** if the actor stops answering, its seat is released with `no-heartbeat`, and the rehearsal fails.

## Exit codes

| Code | Means |
|---|---|
| 0 | Every cue was reported `done`, and every `verify` check passed. |
| 1 | The rehearsal ran, but a cue failed, a check failed, or the seat was lost. |
| 2 | The files have problems, or nothing could start. |

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
