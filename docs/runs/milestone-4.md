# Milestone 4: recorded runs

Run on 2026-10-24. Every result below ran; nothing is projected. Claims about milestone 4 in the docs point here.

## What ran

The example play `examples/plays/slug-kata/` (D40), started with one command:

```bash
zanni examples/plays/slug-kata/play.yaml
```

The director read the script (`examples/scripts/slug-kata/`), started its local seats (one tester, up to two coders), and ran the script through its tools (D33). A tester wrote failing tests, checked by the verifier `tests-fail`. The owner approved the `plan` gate with `zanni gate`. Then one or two coders made the tests pass, checked by `tests-pass`. Round 2 extends `slugify` with `max_length`.

Each run used a fresh copy of `examples/`, a new join token and a new owner token, all three kept out of every log. A driver script played the owner. It started the director in the background, with its standard input closed (as `nohup` would), and decided each gate from another process with `zanni gate <play> approve` (or `reject`). The configuration decided every model: the driver only wrote each copy's `models:` before starting.

Three layouts:

| Layout | The director | The tester | The coders | Models |
|---|---|---|---|---|
| **One machine, local** | machine A | local seat on A | 1–2 local seats on A | everything on `qwen3.8:27b`, on a local model server |
| **One machine, cloud** | machine A | local seat on A | 1–2 local seats on A | everything on `claude-haiku-5-5` |
| **Two machines** | machine A, at `0.0.0.0:8765` | local seat on A | one actor joining from machine B, on the same network | `qwen3.8:27b`: the director and tester on the same local model server, the coder on machine B's own |

For the two-machine runs, the play's `coder` part was set to one seat with no local seat listed, so the coder could only come from an actor joining. On machine B, the code was a copy of machine A's working tree, installed with `uv sync` from the same `uv.lock`, with no API key and no `.env`. The actor there had its own configuration (`coder-remote`, role `./examples/roles/slug-coder`, its own model) and joined three directors in turn.

| Component | Version |
|---|---|
| zanni | `director-and-casting` at `1641293` (item 9), plus the fixes in item 10's commit, described below |
| Python | 3.14.4 on machine A; 3.14.7 on machine B (from `.python-version`) |
| a2a-sdk | 1.2.3 |
| mcp | 2.3.0 |
| pydantic-ai-slim | 2.60.0 |
| genai-prices | 0.1.13 |
| git | 2.46.1 |
| uv | 0.10.4 |
| Ollama server | 0.40.6, on both model servers |
| `qwen3.8:27b` | 27.3B, Q4_K_M, native tool calling, `price: { input: 0, output: 0 }` in each configuration; digest `aaee06c39dcf` on machine A's model server |
| `claude-haiku-5-5` | Anthropic API, priced by genai-prices |

## Results

The director's time, tokens and cost are shown apart from the seats'. **Time** runs from `run-started` to `run-stopped` in the play's log. **Tokens** are input / output, summed over the director's turns or over a seat's cues. Seat numbers come from each actor's own log (D32), whose `cost` events carry tokens.

### One machine, local models

| Run | Result | Rounds | Verdicts | Time (s) | Director: turns, tokens | Tester: cues, tokens | Coders: cues, tokens | Cost | Exit |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ✅ done | 2 | 4 / 4 passed | 353 | 2, 95636 / 4001 | 2, 9963 / 944 | coder-1 2, 10654 / 1499; coder-2 1, 7250 / 532 | $0 (configured) | 0 |
| 2 | ✅ done | 2 | 4 / 4 passed | 667 | 1, 124688 / 3622 | 2, 9570 / 884 | coder-1 2, 15361 / 3351; coder-2 1, 3690 / 364 | $0 (configured) | 0 |
| 3 | ✅ done | 2 | 4 / 4 passed | 1260 | 1, 135380 / 4170 | 2, 11048 / 1607 | coder-1 2, 18939 / 8458; coder-2 1, 5536 / 643 | $0 (configured) | 0 |

### One machine, cloud models

| Run | Result | Rounds | Verdicts | Time (s) | Director: turns, tokens, cost | Tester: cues, tokens, cost | Coders: cues, tokens, cost | Total | Exit |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ✅ done | 2 | 4 / 4 passed | 57 | 1, 136821 / 3161, $0.0152626 | 2, 17097 / 2059, $0.0027392 | coder-1 2, 12652 / 2154, $0.0023422; coder-2 1, 5312 / 542, $0.0008022 | $0.0211462 | 0 |
| 2 | ✅ done | 2 | 4 / 4 passed | 56 | 1, 107864 / 3244, $0.0124084 | 2, 16409 / 1987, $0.0026344 | coder-1 2, 15769 / 2275, $0.0027144; coder-2 1, 5939 / 644, $0.0009159 | $0.0186731 | 0 |
| 3 | ✅ done | 2 | 4 / 4 passed | 56 | 1, 181204 / 4666, $0.0204534 | 2, 16720 / 1805, $0.0025745 | coder-1 3, 21355 / 2519, $0.0033950; coder-2 never cued | $0.0264229 | 0 |

The director's own share of the cloud spend was 72%, 66% and 77%.

### Two machines

| Run | Result | Rounds | Verdicts | Time (s) | Director: turns, tokens | Tester (machine A): cues, tokens | Coder (machine B): cues, tokens | Cost | Exit |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ✅ done | 2 | 4 / 4 passed | 1137 | 1, 144257 / 4029 | 2, 15135 / 2506 | 3, 16618 / 2778 | $0 (configured) | 0 |
| 2 | ✅ done | 2 | 4 / 4 passed | 1036 | 1, 133877 / 4534 | 2, 12725 / 1910 | 2, 15935 / 4008 | $0 (configured) | 0 |
| 3 | ✅ done | 2 | 4 / 4 passed | 437 | 2, 82458 / 3420 | 2, 12195 / 1687 | 2, 10841 / 3507 | $0 (configured) | 0 |

The coder's numbers come from its own log on machine B. Per cue: run 1 had 4165 / 414, 4032 / 318 and 8421 / 2046; run 2 had 8226 / 2142 and 7709 / 1866; run 3 had 4628 / 881 and 6213 / 2626. Its log ends each run with `released`, reason `done`. In every run, the coder seat was played by `coder-remote` from machine B. It reached the stage through the director's MCP server.

### Once each

| Run | What it showed | Result | Time (s) | Exit |
|---|---|---|---|---|
| **Recast** | coder-1 killed with `SIGKILL` 4 s into its cue | ✅ done, 2 rounds, 4 / 4 verdicts | 371 | 0 |
| **Pause** | the director's model server stopped mid-play, then restarted | ✅ done, 2 rounds, 4 / 4 verdicts | 424 | 0 |
| **Gate** | `plan` rejected with a note, then approved | ✅ done, 2 rounds, 5 / 5 verdicts | 511 | 0 |
| **Budget, seats priced** | a $0.30 budget, the seats at a declared $100 per million tokens, the director at $0 | two cues ended `over-budget` by the actor; the director stopped with $0.0377 left | 402 | 1 |
| **Budget, all priced** | the same, with the director also at $100 per million tokens | stopped with reason `budget` after the director's first model response | 27 | 1 |
| **Unpriced** | a tester whose model has no price, under a budget | refused at join (`unpriced`), as it should; then stopped by hand | 150 | 1 |

All on `qwen3.8:27b`. The budget runs declared a price for the local model, so the budget had something to count, at no real spend.

**Recast.** The coders had just been given their cues (`r1-c2` and `r1-c3`). The driver killed `coder-1`'s process. The director saw its exit at once (`seat-exited`, code -9) and released the seat (`no-heartbeat`). It restarted the local seat (restart 1 of 2), which rejoined as seat `coder-3`, and resent the cue to it as `r1-c2-again` (`cue-resent`, `was: coder-1`). The new seat completed it, and the play went on to done. From the kill to the resent cue took 2 s.

**Pause.** The director's model went through a proxy the driver controlled. The driver stopped it after the first reports. The director's next model request failed (`fallback`, reason `error`), so with no model left the play paused (`paused`). The driver restarted the proxy and resumed with `zanni gate <play> resume --note …`. The director logged `resumed` (by `owner`) and finished the play.

**Gate.** The director ran in the background, and the driver decided from another process. At the first `gate-pending`, the driver ran `zanni gate <play> reject --note "Also cover an input that is only punctuation, such as '!!!', which slugifies to an empty string."`. The director cued the tester again, as "Round 1 (revision)", with the note. It reran `tests-fail` and asked the gate again 57 s after the rejection, and the driver approved it. The play went on to done, with the plan gate asked again in round 2. The first try of this run, on the code before item 10's fixes, found finding 5. It ended `stalled-state` after 34 minutes, with exit 1.

**Budget, seats priced.** The director gave the tester a cue with a budget of $0.08. The tester's first model response already cost more, so its engine ended the cue there. It reported `outcome: over-budget`, "Stopped at the cue's budget of $0.08, after spending $0.1390.", with no changes. The director then asked for a cue the rules refused: "a cue may have at most $0.0805 now (the unreserved budget, shared among 2 idle seat(s))". It retried within that limit, and the second cue also ended `over-budget`, at $0.1233. With $0.0377 left, below one model call, the director stopped the play itself, not as done: "Budget exhausted before Round 1 could be completed …". The spend was $0.2623, under the budget.

**Budget, all priced.** With the director also priced, its first model response (5299 input and 539 output tokens) cost $0.5838, above the $0.30 budget. Its turn ended there, before that response's tool calls ran, and the run stopped with reason `budget`, exit 1. One model call is the overshoot, as D39 now says. The first try of this run, before the change, is finding 7.

**Unpriced.** Under a $1.00 budget, the tester's configuration had a model with no `price:`. The director refused its join (`join-refused`, reason `unpriced`), and the seat's process printed the reason and exited with code 2:

```
Joining the play 'slug-kata' (script ../../scripts/slug-kata) at http://127.0.0.1:…
Refused: unpriced: this play has a budget, and the actor's models aren't all priced, so its cost would be unknown; add `price:` to each model entry in its configuration (D7)
```

The director restarted the seat twice, which was refused the same way each time (`seat-not-restarted` after the second). It then waited for a tester to join, as the tester part has a minimum of one seat, until the driver stopped it by hand after 150 s (`interrupted`, exit 1). The first try of this run found finding 6a: each refused seat exited with `SIGABRT` (-6) instead of 2.

### Totals

| Layout | Done |
|---|---|
| One machine, local | 3 / 3 |
| One machine, cloud | 3 / 3 |
| Two machines | 3 / 3 |

These are nine runs of one small kata. They show a play runs end to end in each layout, not how good these models are as directors.

**Cloud spend:**

| What | Spend |
|---|---|
| The three cloud runs | $0.0662422 (directors $0.0481244, seats $0.0181178) |
| A cloud run before the example's stage was fixed (see below) | $0.0173036 (director $0.0122727) |
| A play started by mistake, in a test of the driver, and stopped by hand | $0.0014238 logged for one seat. Its director's turn was interrupted, so that turn's cost was never logged. |
| **Logged in all** | **$0.0849696** |

All of it was on `claude-haiku-5-5`. Every other run was on a local model at a configured price of $0.

### Two logs, one run

Each side keeps its own log (D32). The play's, on machine A, for cloud run 1 (`log/<run-id>.jsonl` in the play folder):

```json
{"ts": "2026-10-24T18:54:39Z", "event": "run-started", "play": "slug-kata", "script": {"ref": "../../scripts/slug-kata", "commit": null, "hash": "sha256:9959c549…"}}
{"ts": "2026-10-24T18:54:39Z", "event": "seat-started", "seat": "tester-1", "part": "tester", "pid": 74662}
{"ts": "2026-10-24T18:54:39Z", "event": "seat-started", "seat": "coder-1", "part": "coder", "pid": 74663}
{"ts": "2026-10-24T18:54:41Z", "event": "actor-joined", "seat": "tester-1", "part": "tester", "role": "../../roles/slug-tester", "actor": "tester-1", "models": [{"provider": "anthropic", "model": "claude-haiku-5-5"}]}
{"ts": "2026-10-24T18:54:44Z", "event": "cue", "seat": "tester-1", "scene": "Scene 1: Specify", "cue": "r1-c1", "budget": "0.3"}
{"ts": "2026-10-24T18:54:51Z", "event": "report", "seat": "tester-1", "scene": "Scene 1: Specify", "cue": "r1-c1", "outcome": "done", "summary": "I wrote the two test files. I have no way to run pytest from here, so I haven't confirmed …", "changes": ["1", "2"]}
{"ts": "2026-10-24T18:54:51Z", "event": "cost", "seat": "tester-1", "model": "claude-haiku-5-5", "amount": "0.0014260"}
{"ts": "2026-10-24T18:54:52Z", "event": "verdict", "scene": "round 1", "verifier": "tests-fail", "kind": "hard", "passed": true, "detail": "…NotImplementedError…", "source": "script"}
{"ts": "2026-10-24T18:54:54Z", "event": "gate-pending", "gate": "plan", "summary": "Round 1 tests written (tests/test_slug.py: AC1-AC2; tests/test_words.py: AC3-AC4). tests-f…"}
{"ts": "2026-10-24T18:54:55Z", "event": "gate", "gate": "plan", "decision": "approved", "by": "owner", "note": "ok"}
{"ts": "2026-10-24T18:54:57Z", "event": "seat-started", "seat": "coder-2", "part": "coder", "pid": 74837}
{"ts": "2026-10-24T18:54:59Z", "event": "cue", "seat": "coder-1", "scene": "Scene 2: Build (item slugify)", "cue": "r1-c2", "budget": "0.3"}
{"ts": "2026-10-24T18:54:59Z", "event": "cue", "seat": "coder-2", "scene": "Scene 2: Build (item word_count)", "cue": "r1-c3", "budget": "0.3"}
{"ts": "2026-10-24T18:55:08Z", "event": "verdict", "scene": "round 1", "verifier": "tests-pass", "kind": "hard", "passed": true, "detail": "4 passed …", "source": "script"}
{"ts": "2026-10-24T18:55:10Z", "event": "round-ended", "round": 1, "reason": "tests-pass passed for round 1; backlog/round-2.md is next."}
{"ts": "2026-10-24T18:55:11Z", "event": "cue", "seat": "tester-1", "scene": "Scene 1: Specify (round 2)", "cue": "r2-c4", "budget": "0.2"}
{"ts": "2026-10-24T18:55:17Z", "event": "report", "seat": "tester-1", "scene": "Scene 1: Specify (round 2)", "cue": "r2-c4", "outcome": "done", "summary": "I added `test_ac5_slugify_max_length_cuts_at_last_dash_that_fits` to `tests/test_slug.py`.…", "changes": ["5"]}
{"ts": "2026-10-24T18:55:32Z", "event": "verdict", "scene": "round 2", "verifier": "tests-pass", "kind": "hard", "passed": true, "detail": "5 passed …", "source": "script"}
{"ts": "2026-10-24T18:55:33Z", "event": "stop-note", "note": "Both backlog rounds complete: round 1 (slugify, word_count) and round 2 (slugify max_lengt…"}
{"ts": "2026-10-24T18:55:34Z", "event": "cost", "seat": "director", "model": "anthropic claude-haiku-5-5", "amount": "0.0152626", "input_tokens": 136821, "output_tokens": 3161}
{"ts": "2026-10-24T18:55:34Z", "event": "seat-released", "seat": "tester-1", "reason": "done"}
{"ts": "2026-10-24T18:55:36Z", "event": "run-stopped", "reason": "done", "completed": true, "spend": "0.0211"}
```

The tester's own log, at `<state_dir>/plays/slug-kata/<run-id>/log.jsonl`:

```json
{"ts": "2026-10-24T18:54:41Z", "event": "joined", "director": "http://127.0.0.1:57413", "play": "slug-kata", "script": "../../scripts/slug-kata", "seat": "tester-1", "part": "tester", "permissions": {"read": ["vision.md", "backlog/", "spec/", "tests/"], "write": ["tests/"]}, "expires_at": "2026-10-25T18:54:41Z"}
{"ts": "2026-10-24T18:54:44Z", "event": "cue", "seat": "tester-1", "scene": "Scene 1: Specify", "cue": "r1-c1"}
{"ts": "2026-10-24T18:54:51Z", "event": "report", "seat": "tester-1", "cue": "r1-c1", "outcome": "done", "summary": "I wrote the two test files. I have no way to run pytest from…", "changes": ["1", "2"]}
{"ts": "2026-10-24T18:54:51Z", "event": "cost", "seat": "tester-1", "model": "anthropic claude-haiku-5-5", "amount": "0.0014260", "input_tokens": 8470, "output_tokens": 1158}
{"ts": "2026-10-24T18:55:12Z", "event": "cue", "seat": "tester-1", "scene": "Scene 1: Specify (round 2)", "cue": "r2-c4"}
{"ts": "2026-10-24T18:55:17Z", "event": "report", "seat": "tester-1", "cue": "r2-c4", "outcome": "done", "summary": "I added `test_ac5_slugify_max_length_cuts_at_last_dash_that_…", "changes": ["5"]}
{"ts": "2026-10-24T18:55:17Z", "event": "cost", "seat": "tester-1", "model": "anthropic claude-haiku-5-5", "amount": "0.0013132", "input_tokens": 8627, "output_tokens": 901}
```

The play's log is trimmed to the tester's events and the play's milestones; the `run` field and long texts are cut short. Neither log holds a token. The tester's log has no `released` event: the director closed its pipe before the release reached it (finding 6b below).

### The director's tool calls the rules refused

The director's tools check the rules in code first (D33). A refusal is logged as `tool-refused`, and the model reads the reason and carries on. In the nine layout runs and the two passing once-each runs:

| Run | Tool | Reason given to the model |
|---|---|---|
| local 1, local 2 | `cue` | there is no seat or part 'coder-2'; the seats are: coder-1, tester-1; the parts: tester, coder |
| cloud 3 | `cue` ×2 | coder-1 is still working on a cue; wait_for_reports first |
| cloud 3 | `cue` | there is no seat or part 'coder-2'; … |
| two machines 1, 3 | `cast` | coder may have 1 seat(s); 2 is outside that |
| two machines 2 | `cue` | this seat may not read app/; it may read: vision.md, backlog/, spec/, tests/, … |

In each case the model then did what the reason said. It cast a second coder before cueing it, waited for reports, kept to one coder, or gave the tester readable paths. In cloud run 3, coder-1 did both builds in turn, and coder-2 was never cued.

## What the runs found, and what changed

Runs before the recorded ones, and first tries of the once-each runs, found these. The recorded runs above were made after changes 1 to 4. The fixes for 5 to 7 came after the layout runs, so the layout runs ran without them; the reruns of the gate, budget and unpriced runs ran with them.

1. **"Done" was read from a sentence.**
   - **What happened:** a local director finished the kata correctly, then called `stop("done: Round 2 was the last backlog file; …")`. Only a reason of exactly `done` asked for done, so the run ended as not completed, with exit 1.
   - **The change:** `stop` takes a separate `done` flag (D42). A test in `tests/test_verifiers.py` covers it.
2. **A local seat's output was lost.** Its output went to a file through a pipe, buffered, and a seat stopped through its pipe lost what was still in the buffer. Local seats now run unbuffered (`PYTHONUNBUFFERED`), and a seat flushes before it exits.
3. **Tokens weren't logged.** The `cost` events of the director and of each actor now carry `input_tokens` and `output_tokens`. This record's token counts come from them.
4. **The example's stage gave round 2 away.**
   - **What happened:** `spec/slug.md` described `max_length` from the start, so round 1's coder implemented it. In round 2, the tester's new test passed at once, and `tests-fail` couldn't pass. A cloud director stopped honestly: "Round 2 cannot meet the Scene 1 check honestly …" (exit 1, $0.0173036).
   - **The change:** the spec leaves `max_length` to `backlog/round-2.md`, and the stub is `def slugify(text: str) -> str`.
5. **A released local seat couldn't be cast again.**
   - **What happened:** in the gate run's first try, the director released both coders at the end of round 1. In round 2, `cast` refused: "every local seat listed for coder is already started (2)". The director tried `cast`, `cue` and `release` 41 times over six turns, then stopped (`stalled-state`).
   - **The change:** a released local seat can be started again by a later `cast` (added to D36). `test_a_released_local_seat_can_be_cast_again_for_a_later_scene` fails without the change.
6. **Seats' exit codes were wrong.**
   - **a. A refused seat crashed.** A local seat refused at join, or released mid-play, exited with `SIGABRT` (-6): "Fatal Python error: _enter_buffered_busy: could not acquire lock for <_io.BufferedReader name='<stdin>'> at interpreter shutdown". The thread watching the director's pipe held standard input's lock as the seat exited normally. It now reads the pipe with `os.read`. `test_a_local_seat_that_cant_join_exits_cleanly_while_watching_its_pipe` fails without the change.
   - **b. Released seats exited with 1.** At the end of a play, the director closed each seat's pipe right after releasing it, so the seat stopped through its pipe (exit 1) before it saw its release. That's why its own log has no `released` event in the logs above. A released seat now gets 5 s to exit on its own first (D36), and the end-to-end test asserts exit 0.
7. **The director's own spend wasn't held to the budget.**
   - **What happened:** in the budget run's first try, the local director was priced at $100 per million tokens, under a $0.30 budget. It played in one turn of 60333 input tokens, at $6.4538, because D39 checked the budget only before a turn. The seats' cues were held to their budgets meanwhile.
   - **The change:** the director's spend is counted after each of its model responses, before that response's tool calls run, and the turn ends at the budget (D39, amended; Alessio's call). `test_the_directors_own_spend_counts_response_by_response_and_ends_its_turn_at_the_budget` covers it.
8. **A failed turn's spend went uncounted.** In the pause run, the director's model failed mid-turn, and nothing that turn had spent was logged or charged. With priced models, that's spend counted as zero, against D7. A turn whose models all fail now charges and logs what it spent (D39). `test_a_turn_whose_models_all_fail_still_charges_what_it_spent` covers it.

Not changed, and recorded:

- **Directors play in one turn.** In all 12 passing runs above, the director ran the whole kata in one or two turns, with 80k to 180k input tokens, since each tool result stays in the turn's context. That made the director 66–77% of the cloud spend. The turn cap (`max_director_turns`) and the per-turn request cap still hold. Shorter turns, or trimming old tool results, are for later (`TODO.md`).
- **Gates count once per play.** Local run 1 and two-machine run 3 asked the `plan` gate in round 1 only. The rules check that each enforced gate has been approved in the play, not in each round, so round 2's coders started without a second approval. Per-round gates are for later (`TODO.md`).
- **One model call can overshoot a cue's budget many times over.** The actor checks after each model response (D39). With a small cue budget and an expensive call, one call is the whole overshoot.
- **A seat refused at join is restarted anyway.** A refusal such as `unpriced` won't change on a restart, but the director restarts the seat twice before giving up.
- **A part whose local seats are all refused waits for an actor to join.** The unpriced run waited until stopped by hand. The stop rules can't end a play that has no turns yet.
- **An interrupted turn's cost is lost.** A director stopped by hand (`SIGINT`) mid-turn never logs that turn's cost. That happened once, in the play started by mistake.

## Timing

Local runs took 353 s to 1260 s; cloud runs about a minute. Almost all of the local time was the model. The director typically played the whole kata in one turn of 80k to 180k input tokens on `qwen3.8:27b` (see "Not changed" below). Local runs 2 and 3 overlapped the first two two-machine runs, and the director and tester of both layouts shared one local model server. Their times include waiting for it.
