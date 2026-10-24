# Milestone 3: recorded runs

Run on 2026-10-24. Every result below ran; nothing is projected. Claims about milestone 3 in the docs point here.

## What ran

The `smoke` rehearsal of the example role `slug-tester` (`examples/roles/slug-tester/`), as in [milestone 2](milestone-2.md): one cue, "write one pytest test for each acceptance criterion", and a `pytest` verifier on the stage afterwards. This time the director and the actor were **two `zanni` processes talking over A2A**:

```bash
# the director
ZANNI_JOIN_TOKEN=… zanni examples/roles/slug-tester/rehearsals/smoke.yaml --serve --listen 0.0.0.0:8765
# the actor: a configuration whose play is http://<director's machine>:8765
zanni slug-tester.yaml
```

The actor fetched the director's card, joined with the join token, was cast, reached the stage through the director's MCP server, answered the cue with a report, and was released. Each run used a fresh copy of the stage, and a new join token.

Two layouts:

| Layout | The director | The actor | The actor's model |
|---|---|---|---|
| **One machine** | on machine A, at `127.0.0.1` | on machine A | `qwen3.8:27b` on a local model server on a second machine, or `claude-haiku-5-5` |
| **Two machines** | on machine A, at `0.0.0.0:8765` | on machine B, on the same network, reaching A by its LAN address | `qwen3.8:27b` on machine B's own model server |

On machine B, the code was a copy of machine A's working tree, installed with `uv sync` from the same `uv.lock`. Nothing else was installed there but uv; no API key and no `.env`.

| Component | Version |
|---|---|
| zanni | `actor-over-a2a` at `6f1e01c` (item 6), plus the release fix described below |
| Python | 3.14.4 on machine A; 3.14 on machine B (from `.python-version`) |
| a2a-sdk | 1.2.3 |
| mcp | 2.3.0 |
| pydantic-ai-slim | 2.60.0 |
| uvicorn | 0.54.0 |
| httpx / httpx2 | 0.28.1 / 2.16.0 |
| sse-starlette | 3.5.0 |
| Ollama server | 0.40.6 |
| `qwen3.8:27b` | digest `aaee06c39dcf`, 27.3B, Q4_K_M, native tool calling |
| `claude-haiku-5-5` | Anthropic API |

## Results

### One machine

| Model | Run | Verifier | Actor time (s) | Cue (s) | Tool calls | Tokens in / out | Cost | Exit (actor / director) |
|---|---|---|---|---|---|---|---|---|
| qwen3.8:27b | 1 | ✅ 2 passed | 12.6 | 9 | 4 | 3369 / 298 | $0 (configured) | 0 / 0 |
| qwen3.8:27b | 2 | ✅ 2 passed | 14.8 | 11 | 4 | 3413 / 356 | $0 (configured) | 0 / 0 |
| qwen3.8:27b | 3 | ✅ 2 passed | 15.1 | 13 | 4 | 4458 / 348 | $0 (configured) | 0 / 0 |
| claude-haiku-5-5 | 1 | ✅ 2 passed | 7.6 | 4 | 4 | 4979 / 481 | $0.0007384 | 0 / 0 |
| claude-haiku-5-5 | 2 | ✅ 2 passed | 7.2 | 4 | 4 | 4926 / 420 | $0.0007026 | 0 / 0 |
| claude-haiku-5-5 | 3 | ✅ 2 passed | 6.7 | 4 | 4 | 4926 / 431 | $0.0007081 | 0 / 0 |

- **Actor time:** wall clock for the actor's `zanni` command, from start to exit: start-up, fetching the card, joining, the cue, the release.
- **Cue:** from the `cue` event to the `report` event in the director's log, which has a resolution of one second.
- **Costs:** Haiku's come from published prices (genai-prices, through Pydantic AI), reported by the actor and logged by the director. The local model's come from the `price: { input: 0, output: 0 }` in its configuration (D7).

### Two machines

| Model | Run | Verifier | Cue (s) | Tool calls | Tokens in / out | Cost | Exit (actor / director) |
|---|---|---|---|---|---|---|---|
| qwen3.8:27b | 1 | ✅ 2 passed | 241 | 4 | 3403 / 362 | $0 (configured) | 0 / 0 |
| qwen3.8:27b | 2 | ✅ 2 passed | 289 | 4 | 3349 / 307 | $0 (configured) | 0 / 0 |
| qwen3.8:27b | 3 | ✅ 2 passed | 59 | 4 | 3469 / 404 | $0 (configured) | 0 / 0 |

The director served three times in a row; the actor ran three times in a loop on machine B. The actor's stream never dropped (no "the task's stream dropped" line). The cue times vary for a reason unrelated to the network; see [Timing](#timing).

### Totals

| Layout | Model | Passed |
|---|---|---|
| One machine | qwen3.8:27b | 3 / 3 |
| One machine | claude-haiku-5-5 | 3 / 3 |
| Two machines | qwen3.8:27b | 3 / 3 |

Nine runs on one small task: they show the protocol works between processes and between machines, not how good these models are.

### Two logs, one run

Each side keeps its own log (D32). The director's, on machine A, for the third two-machine run:

```json
{"ts": "2026-10-24T11:12:13Z", "event": "run-started", "play": "rehearsal:smoke", "script": "…/slug-tester/rehearsals/smoke.yaml"}
{"ts": "2026-10-24T11:12:19Z", "event": "actor-joined", "seat": "slug-tester-1", "part": "slug-tester", "role": "./zanni-m3/examples/roles/slug-tester", "actor": "slug-tester-remote", "models": [{"provider": "ollama", "model": "qwen3.8:27b"}]}
{"ts": "2026-10-24T11:12:19Z", "event": "cue", "seat": "slug-tester-1", "scene": "Specify", "cue": "smoke-1"}
{"ts": "2026-10-24T11:13:18Z", "event": "report", "seat": "slug-tester-1", "scene": "Specify", "cue": "smoke-1", "outcome": "done", "summary": "Wrote `tests/test_slug.py`: …"}
{"ts": "2026-10-24T11:13:18Z", "event": "cost", "seat": "slug-tester-1", "model": "qwen3.8:27b", "amount": "0"}
{"ts": "2026-10-24T11:13:18Z", "event": "seat-released", "seat": "slug-tester-1", "reason": "done"}
{"ts": "2026-10-24T11:13:19Z", "event": "verdict", "scene": "verify", "verifier": "tests-pass", "kind": "hard", "passed": true, "detail": "2 passed in 0.02s"}
{"ts": "2026-10-24T11:13:19Z", "event": "run-stopped", "reason": "rehearsal finished"}
```

The actor's, on machine B, at `<state_dir>/plays/rehearsal-smoke/<run-id>/log.jsonl`:

```json
{"ts": "2026-10-24T11:12:19Z", "event": "joined", "director": "http://<machine A>:8765", "play": "rehearsal:smoke", "seat": "slug-tester-1", "part": "slug-tester", "permissions": {"read": ["vision.md", "backlog/", "spec/", "tests/"], "write": ["tests/"]}, "expires_at": "2026-10-25T11:12:19Z"}
{"ts": "2026-10-24T11:12:20Z", "event": "cue", "seat": "slug-tester-1", "scene": "Specify", "cue": "smoke-1"}
{"ts": "2026-10-24T11:13:18Z", "event": "report", "seat": "slug-tester-1", "cue": "smoke-1", "outcome": "done", "summary": "Wrote `tests/test_slug.py`: …", "changes": ["1"]}
{"ts": "2026-10-24T11:13:18Z", "event": "cost", "seat": "slug-tester-1", "model": "ollama qwen3.8:27b", "amount": "0"}
{"ts": "2026-10-24T11:13:19Z", "event": "released", "seat": "slug-tester-1", "reason": "done"}
```

The `run` field and the full summaries are trimmed here. Neither log holds a token. The clocks of the two machines agree to within a second.

### A wrong join token

The actor presented a join token that wasn't the play's. It was refused at once, exit code 2, in 2.3 s:

```
Joining the play 'rehearsal:smoke' (script …/smoke.yaml) at http://127.0.0.1:54920
Refused: not-authorised: the join token is missing, or isn't this play's
```

The director logged `join-refused` and kept waiting for an actor that fits, as it should; it was then stopped by hand (exit code 1, "Stopped before the rehearsal finished."). The actor's own log recorded the same `join-refused`.

### Losing the actor

The actor (on `claude-haiku-5-5`) was killed with `SIGKILL` 3.5 s after it started, while its cue ran. With the default heartbeat (`interval` 30 s, `misses` 3), the director:

1. noticed the dropped stream and the missing contact, and released the seat with `no-heartbeat`, **98 s after the cue** (90 s, plus up to one 10 s check of its heartbeat watch);
2. revoked the seat's tokens, failed the cue, ran `verify`, which failed ("no tests ran"), and stopped with exit code 1 ("Rehearsal FAILED").

## What the runs found, and what changed

1. **The actor waited for a status that never came.**
   - **What happened:** in a trial run before the recorded ones, the director released the seat, verified and exited at once. The actor had sent `zanni.released`, but kept following the task for its final `completed` status. The server was gone, so the actor polled for 90 s, gave up, and exited 1 as "lost", although its seat had ended with `done`.
   - **The change:** an actor's seat is over once it has been released; it stops following the task there (`src/zanni/actor/seat.py`). A stream that drops now prints "the task's stream dropped (…); polling", so it shows in the output. Tested by `test_the_actor_is_done_when_released_even_if_the_director_stops_at_once` (`tests/test_actor_seat.py`), which passes in-process even without the fix; the runs above, made after it, are its real test.
2. **The director cut the actor's stream when it stopped.**
   - **What happened:** the director printed `ERROR: ASGI callable returned without completing response.` in every two-machine run, in 2 of the 3 one-machine `qwen3.8:27b` runs and in one trial run, and never in the faster Haiku runs, after its verify step. The runs still passed. The actor's task stream (`SubscribeToTask`) was sometimes still open when the director stopped: a2a-sdk ends a subscription only when the task's event queue shuts down, which happens asynchronously after `completed`. uvicorn's shutdown made sse-starlette, which both a2a-sdk and `mcp` stream with, abandon the response mid-stream. The actor's side would have seen `incomplete chunked read`.
   - **The change:** before stopping its server, the director now closes the A2A request handler, which ends every task's event queue, so open streams end cleanly. It then waits up to 2 s for requests still in flight (`src/zanni/engine/serve.py`, `src/zanni/engine/a2a_server.py`).
   - **Checked:** a scripted actor, with four stage calls like the real model's, reproduced the error in 3 of 12 runs before the change and in 0 of 12 after. `test_stopping_the_director_ends_an_open_task_stream_cleanly` (`tests/test_serve.py`) keeps a stream open while the director stops: it fails without the change and passes with it, in 0.21 s.
   - **Not re-measured:** the change was made after the two-machine runs above, which ran without it.

## Timing

The cue times of `qwen3.8:27b` ranged from 9 s to 289 s on the same task, with about the same tokens. To tell whether Zanni caused that, the same rehearsal was run in-process (no served director) on milestone 2's code, at `master`, and on this branch, alternately:

| Code | Run time (s) |
|---|---|
| this branch | 66 |
| milestone 2 (`master`) | 466 |
| this branch | 1086 |
| milestone 2 (`master`) | 18 |

Both codebases were slow and fast in turn, with similar tokens (3350 to 6005 in), so the variance was in the model server, not in Zanni or the network. The server had the model loaded with a 131,072-token context rather than the 32,768 its configuration asks for; Zanni doesn't set a context length. The two-machine cue times above (241 s, 289 s, then 59 s) came from the same server.

## Spend

Cloud spend: **$0.0021491**, the three Haiku runs, plus the killed Haiku run, whose cost wasn't recorded because the actor was killed before it reported: at most one or two requests, a fraction of a cent. The cap was $1.00. Local runs cost nothing per token.

## Surprises

- **Released is the end of a seat, for the actor.** The protocol's last word on a seat is the director's `completed`, but an actor can't count on the director still being there to send it. The fix made the actor's side match how the director behaves.
- **A clean shutdown needs the server's help.** Both SDKs stream with sse-starlette, which drops open streams when uvicorn stops. The director must end its streams itself before stopping.
- **The model server, not the network, set the pace.** A cue across the network was as fast as one on loopback when the server was fast (59 s against 9 to 13 s, on a server that varied 18 s to 1086 s on the same work).
- **One trial run stopped before its cue finished,** when its command was interrupted, and isn't counted.
