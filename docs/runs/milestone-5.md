# Milestone 5: recorded runs

Run on 2026-10-24 and 2026-10-25. Every result below ran; nothing is projected. Claims about milestone 5 in the docs point here.

## What ran

Two example plays, one per new stage backend (D51), each started with one command:

- **The slug kata on git** (`examples/plays/slug-kata-git/`). It's the milestone 4 kata, with the stage in a git repository: a bare repository made by the play's `make-remote.py`, standing in for a hosted one. The director cloned it into `log/<run-id>-stage` on the branch `zanni/slug-kata-git/<run-id>`, committed each write with the seat as author, and pushed the branch as `push:` says (D46). The `plan` gate is asked every round, before the coder's cues (D48).
- **Release notes on the `mcp` backend** (`examples/plays/release-notes/`). The stage is the example SQLite stage server (`examples/stage-servers/sqlite/`), reached with the director's stage token (D47). A writer drafts `notes/release-notes.md` from `changelog.md` and `style.md`, and an editor revises it. The verifier `notes-structure` runs on the verifier seat `checker` (D45). Then the `publish` gate is asked.

Each run used a fresh copy of `examples/`, with new join, owner, verifier and stage tokens, kept out of every log. A driver script played the owner. It started the director in the background with its standard input closed, decided each gate from another process with `zanni gate <play> approve`, and for the once-each runs did what the run needed: stopped the director by hand, broke the remote, stopped the stage server. The configuration decided every model: the driver only wrote each copy's `models:` before starting.

Three layouts, as in milestone 4:

| Layout | The director | The other seats | Models |
|---|---|---|---|
| **One machine, local** | machine A | local seats on A | everything on `qwen3.8:27b`, on a local model server |
| **One machine, cloud** | machine A | local seats on A | everything on `claude-haiku-5-5` (the verifier seat runs no model) |
| **Two machines** | machine A, at `0.0.0.0:8765` | the kata's coder, or release notes' verifier seat, on machine B on the same network; the rest local on A | `qwen3.8:27b`: on A's local model server, and on B's own for the coder |

For the two-machine runs:
- **The kata:** the `coder` part was set to one seat with no local seat listed, so the coder could only come from machine B.
- **Release notes:** the director's configuration listed `checker-remote` as its only verifier seat (`verifier_seats: {remote: [checker-remote]}`), and the play's verifier named it in `runs_on`. That seat presented the verifier token, not the join token.

On machine B, the code was a copy of machine A's working tree, installed with `uv sync` from the same `uv.lock`, with no API key and no `.env`.

| Component | Version |
|---|---|
| zanni | `stage-backends` at `7b6759e` (item 9), plus the fixes in item 10's commit, described below |
| Python | 3.14.4 on machine A; machine B as installed by `uv sync` from `.python-version` |
| a2a-sdk | 1.2.3 |
| mcp | 2.3.0 |
| pydantic-ai-slim | 2.60.0 |
| genai-prices | 0.1.13 |
| git | 2.46.1 |
| uv | 0.10.4 |
| Ollama server | 0.40.6 on machine A's model server; machine B's wasn't checked in these runs |
| `qwen3.8:27b` | native tool calling, `price: { input: 0, output: 0 }` in each configuration |
| `claude-haiku-5-5` | Anthropic API, priced by genai-prices |

## Results

As in milestone 4:
- **Time** runs from `run-started` to `run-stopped` in the play's log.
- **Tokens** are input / output, summed over the director's turns or over a seat's cues.
- **Seat numbers** come from each actor's own log (D32).
- **Verdicts** count every verifier run, so a `tests-fail` rerun after the code was written counts as a failed verdict, as the script expects.
- **Pushes** are the git stage's push events that succeeded, out of those tried.

### The slug kata on git

| Run | Result | Rounds | Verdicts passed | Time (s) | Director: turns, tokens, cost | Seats: cues, tokens, cost | Total | Pushes | Exit |
|---|---|---|---|---|---|---|---|---|---|
| cloud a | ✅ done | 2 | 4 / 4 | 71 | 8, 112885 / 5865, $0.0142210 | tester-1 2, 17682 / 2122, $0.0028292; coder-1 2, 17365 / 1960, $0.0027165; coder-2 1, 8133 / 548, $0.0010873 | $0.0208540 | 3 / 3 | 0 |
| cloud b | ✅ done | 2 | 4 / 4 | 78 | 8, 103744 / 4888, $0.0128184 | tester-1 2, 19192 / 2336, $0.0030872; coder-1 2, 17745 / 2123, $0.0028360; coder-2 1, 8535 / 780, $0.0012435 | $0.0199851 | 3 / 3 | 0 |
| cloud c | ✅ done | 2 | 4 / 4 | 72 | 8, 112787 / 5887, $0.0142222 | tester-1 2, 14524 / 1962, $0.0024334; coder-1 2, 21171 / 2591, $0.0034126; coder-2 1, 8225 / 505, $0.0010750 | $0.0211432 | 3 / 3 | 0 |
| local a | ✅ done | 2 | 5 / 5 | 2564 | 7, 105092 / 6368 | tester-1 2, 12280 / 1915; coder-1 2, 13832 / 3443; coder-2 1, 4966 / 515 | $0 (configured) | 3 / 3 | 0 |
| local b | ⏹ stopped by the driver at 3000 s | 2 | 4 / 4 | 2998 | 6, 71054 / 4238 | tester-1 3, 19381 / 2981; coder-1 1, 3604 / 630; coder-2 1, 3408 / 335 | $0 (configured) | 2 / 2 | 1 |
| local c | ⏹ stopped by the driver at 3000 s | 2 | 3 / 3 | 2998 | 5, 71238 / 3306 | tester-1 2, 8403 / 1096; coder-1 1, 5367 / 552; coder-2 1, 5301 / 435 | $0 (configured) | 2 / 2 | 1 |
| local d | ✅ done | 2 | 5 / 5 | 553 | 8, 94073 / 5667 | tester-1 3, 18903 / 2650; coder-1 2, 16286 / 1973; coder-2 1, 3759 / 352 | $0 (configured) | 3 / 3 | 0 |
| local e | ✅ done | 2 | 5 / 5 | 857 | 8, 110826 / 6736 | tester-1 3, 25470 / 3766; coder-1 2, 18950 / 5671; coder-2 1, 7065 / 560 | $0 (configured) | 3 / 3 | 0 |
| two machines | ✅ done | 2 | 4 / 5 | 775 | 9, 97914 / 7656 | tester-1 (A) 2, 11898 / 1215; coder-1 (B) 3, 20423 / 3894 | $0 (configured) | 3 / 3 | 0 |

**The slow local runs.** Local runs b and c reached round 2 with every gate approved, then hit the driver's 3000 s limit with a cue still out. The model server was slow during the batch:
- In run c, the director's first turn took 514 s before its first cue, on 12k input tokens.
- The tester's first cue took 187 s, on about 6k tokens.
- The notes play, run on the same server right after, took 112, 308 and 622 s for the same work.

A probe of the same model after the batch answered a 4k-token prompt in 16.4 s cold and 0.9 s warm. Runs d and e, made after it with the same code and configuration, finished in 553 s and 857 s. So the slowness was the model server's at the time, not the code's. All five runs are listed.

**What the git stage did:**
- In every finished run, the remote got the run's branch at each approved gate and at the end, with one commit per write.
- Each commit's author was the seat that wrote it (`tester-1`, `coder-1`, `coder-2`), and its subject was the cue: for example `r1-c1: Specify`.
- `main` was never touched.
- The two unfinished local runs pushed only at their approved gates, under `push: approved`. Their later work stayed in the run's clone. They ran before finding 2's fix, so the director didn't print the `git push` command for it; the stopped-by-hand runs below show the fixed behaviour.

**The coder on machine B** joined as `coder-1`, from its own configuration (`coder-remote`). It answered three cues, one in round 1 and two in round 2, with 9, 6 and 6 tool calls:

| Cue | Tokens (in / out) |
|---|---|
| round 1 | 6447 / 1461 |
| round 2 | 7740 / 1174 |
| round 2, the fix | 6236 / 1259 |

Its log ends with `released`, reason `done`. It reached the stage through the director's MCP server. The git clone stayed on machine A, as D46 says: actors never touch the repository.

### Release notes on the `mcp` backend

| Run | Result | Verdicts passed (by) | Time (s) | Director: turns, tokens, cost | Seats: cues, tokens, cost | Total | Exit |
|---|---|---|---|---|---|---|---|
| cloud a | ✅ done | 2 / 2 (checker) | 25 | 4, 29972 / 1227, $0.0036107 | writer-1 1, 4895 / 538, $0.0007585; editor-1 1, 5515 / 591, $0.0008470 | $0.0052162 | 0 |
| cloud b | ✅ done | 1 / 1 (checker) | 27 | 4, 25776 / 1300, $0.0032276 | writer-1 1, 4943 / 457, $0.0007228; editor-1 1, 5625 / 607, $0.0008660 | $0.0048164 | 0 |
| cloud c | ✅ done | 2 / 2 (checker) | 26 | 4, 30339 / 1481, $0.0037744 | writer-1 2, 10009 / 975, $0.0014884; editor-1 1, 5545 / 528, $0.0008185 | $0.0060813 | 0 |
| local a | ✅ done | 1 / 1 (checker) | 622 | 4, 21874 / 1084 | writer-1 1, 3738 / 429; editor-1 1, 3855 / 398 | $0 (configured) | 0 |
| local b | ✅ done | 1 / 1 (checker) | 308 | 4, 22251 / 1290 | writer-1 1, 3645 / 486; editor-1 1, 4245 / 514 | $0 (configured) | 0 |
| local c | ✅ done | 1 / 1 (checker) | 112 | 4, 21625 / 947 | writer-1 1, 3634 / 455; editor-1 1, 4606 / 898 | $0 (configured) | 0 |
| two machines | ✅ done | 1 / 1 (checker-remote, on B) | 113 | 4, 25077 / 1115 | writer-1 1, 3613 / 443; editor-1 1, 3956 / 408 | $0 (configured) | 0 |

**Every verdict ran on the verifier seat, not on the director.**
- The seat ran `python3 checks/structure.py` on its own snapshot of the stage, read over MCP, and answered with the exit code.
- On machine B, `checker-remote` joined with its own verifier token, ran one verification ("the notes have both sections and all 5 changes", exit code 0), and was released `done`.
- It runs no model, so it has no tokens or cost.

**The work stayed on the server.** In each run:
- `notes/release-notes.md` was in the stage server's SQLite database, written first by `writer-1` and then by `editor-1`, as the server's own `author` column shows.
- The play's seed folder `stage/` was unchanged.

**The first two-machine attempt failed.** The director started before `checker-remote` was running on machine B. It took its turns anyway, and each `notes-structure` verdict failed with "the verifier seat checker-remote isn't connected". The driver stopped it at 2400 s. That attempt is finding 4 below; the run in the table is the second attempt.

### Once each

| Run | What it showed | Result | Time (s) | Cost | Exit |
|---|---|---|---|---|---|
| Stopped by hand | `push: approved`, SIGINT after the first gate | ⏹ interrupted | 44 | $0.0114852 | 1 |
| Stopped by hand, `push: always` | the same, with `push: always` | ⏹ interrupted | 44 | $0.0111073 | 1 |
| Push fails | the clone's remote pointed at a repository that doesn't exist | ✅ done | 67 | $0.0202971 | 0 |
| Stage server down | release notes; the stage server stopped after the first report, then started again | ✅ done | 38 | $0.0072617 | 0 |
| Uncastable | the kata's coder had one local seat, unpriced under a budget, with `cast_timeout: 60` | ⏹ uncastable | 62 | $0 | 1 |
| Verifier seat with the join token | release notes, plus a verifier seat presenting the join token | ✅ done | 21 | $0.0047224 | 0 |
| By hand, early | the kata, stopped by hand at 25 s, just after the first gate (code before the fixes) | ⏹ interrupted | 23 | $0.0047420 | 1 |

All on `claude-haiku-5-5`, except where noted.

**Stopped by hand: what each `push` setting left.** These two runs answer the open question in D46. The driver approved the `plan` gate, let the coders write, and stopped the director with SIGINT at 45 s.

| Setting | On the remote | Only in `log/<run-id>-stage` | Printed at the end |
|---|---|---|---|
| `push: approved` | 2 commits (the tester's tests, approved at the gate) | 2 more: both coders' code, not yet checked or approved | the `git push` command that publishes the branch |
| `push: always` | all 4 commits (pushed at the gate, then at the end) | nothing | — |

From these runs, Alessio kept `approved` as the default. A remote only gets work that passed a gate or a finished play, and publishing the rest is one printed command away.

**Push fails.** Two seconds in, the driver pointed the clone's `origin` at a path that doesn't exist.
- All three pushes failed and were logged as `push` with `ok: false`: two at approved gates, one at the end.
- The detail named the problem: "'…/nowhere.git' does not appear to be a git repository".
- The play went on to done, and the 6 commits stayed in the clone.

**Stage server down.** The driver stopped the SQLite stage server at 15 s, right after the writer's report. Then:
1. The editor's cue met the stage away. It ended as `failed`, with "the stage stopped answering: …" and what it had spent.
2. The director logged `stage-unavailable` and `paused`, with the reason.
3. The driver started the server again on the same database and port, and resumed with `zanni gate <play> resume --note "the stage server is back"`.
4. The director logged `resumed`, cued the editor again, and the play reached done.

The first try of this run, on the code before item 10's fixes, found finding 1.

**Uncastable.** The coder's only local seat had a model with no `price:` under a $1.00 budget.
- The director refused its join (`join-refused`, reason `unpriced`).
- The seat exited with code 2 and wasn't restarted (`seat-not-restarted`: "it was refused at join, or couldn't start (exit code 2); a restart wouldn't change that").
- After the 60 s `cast_timeout`, the run stopped with reason `uncastable` and exit 1. The director never took a turn.

In milestone 4, the same setup waited until stopped by hand. The first try of this run was a mistake in the driver: it removed the price from a cloud model, which has a published price anyway, so nothing was refused and the play reached done ($0.0194).

**A verifier seat presenting the join token.** While the play ran, the driver started a second verifier seat, `checker`, with `ZANNI_VERIFIER_TOKEN` set to the join token. It was refused, and it exited with code 2:

```text
Refused: not-authorised: a verifier seat joins with the play's verifier token (ZANNI_VERIFIER_TOKEN), never with the join token
```

The play went on, with its real verifier seat, to done.

**By hand, early.** This run used the code before item 10's fixes. The director stopped at 23 s:
- it had pushed at the approved gate;
- it didn't print the push command for the work after it, because a run stopped by hand skipped the end-of-run step (finding 2).

The two "stopped by hand" runs above are its reruns, after the fix.

Two more runs from the first batch aren't in the table: the stopped-by-hand runs on local models. Their seats were priced at a made-up $100 per million tokens, so that the budget would stop the play early. It did, before any cue had written a file, so neither run showed anything about pushing. They cost nothing real.

### Totals

**Cloud spend**, all on `claude-haiku-5-5`, the director's included:

| | Spend |
|---|---|
| 6 runs on the two plays | $0.0781 |
| 3 runs of the milestone 4 kata, on the folder stage, to compare (below) | $0.0616 |
| 7 once-each runs in the tables | $0.0596 |
| first tries replaced by reruns: stage server down, uncastable, push fails | $0.0436 |
| 2 trial runs before the batch | $0.0265 |
| **Total** | **$0.2695**, under the $2.00 cap |

The local runs cost nothing, with `price: 0` in each configuration.

### The director's tool calls the rules refused

Across all runs, the rules refused 42 of the director's tool calls, and each refusal went back to the model as the tool's result:

| Count | Tool | Refusal |
|---|---|---|
| 18 | `cue` | "a cue may have at most $N now (the unreserved budget, shared among N idle seat(s))" |
| 12 | `cue` | "this seat may not read …; it may read: …". The cue asked the seat to read a path outside its part's permissions, such as `pytest.ini` or `app/slug.py` for the tester |
| 7 | `cue` | "there is no seat or part …". The director named a seat that wasn't cast, or made one up (`slug-1`, `words-1`) |
| 2 | `cue` | "no idle seat of coder: 1 cast, all working; wait_for_reports, or cast more" |
| 1 | `cue` | "the gate(s) plan must be approved in this round before coder gets a cue; ask for them with ask_gate first" (D48) |
| 1 | `cast` | "every local seat listed for coder is already started (2); more can only come from actors joining, and this part takes none" |
| 1 | `cast` | "coder may have 1 seat(s); 2 is outside that" |

The director's next call was within the limit each time. The per-round gate held in every git run: the coder got a cue in each round only after that round's `plan` was approved.

## Shorter director turns (G): before and after

Milestone 4's director played the whole kata in one turn of 80k–180k input tokens, and was 66–77% of the cloud spend. Since D49, a turn ends after each long wait: `wait_for_reports` with reports, or `ask_gate`. The next turn starts from a fresh summary.

The same kata, on the same folder stage and cloud model, as milestone 4 ran it:

| | Milestone 4 (3 runs) | Milestone 5 (3 runs) |
|---|---|---|
| Director's turns | 1 each | 7–8 |
| Director's input tokens | 107864–181204 | 99926–112789 |
| Director's cost | $0.0124–0.0205 | $0.0124–0.0148 |
| Director's share of the run's cost | 66–77% | 66–68% |
| Run's total cost | $0.0187–0.0264 | $0.0189–0.0218 |
| Result | 3 done | 3 done |

The kata on git, cloud: the director's input was 103744–112885 tokens in 8 turns, and 64–68% of the cost.

**What changed:** each turn's prompt is small, at 8k–20k input tokens. The worst case is gone: no run reached milestone 4's 181k tokens or 77%.

**What didn't change:** the total. Each new turn sends the director's instructions and the summary again, so the director's total input stays around 100k–113k, and its share around two thirds. Cutting that is for later, in `TODO.md`.

## What the runs found, and what changed

Fixed in item 10's commit, each with a test:

1. **A seat crashed when the `mcp` stage went away.** The stage tools turned `unavailable` into a request to the model to retry. After one retry, Pydantic AI gave up with an exception the runner didn't expect, and the actor exited with code 1.
   - The director restarted the seat into the same outage twice.
   - Then it waited out `cast_timeout`, 10 minutes, and stopped with `uncastable`. It never paused, because its own turn hadn't touched the stage.

   Now:
   - a cue that meets `unavailable` ends as `failed`, with what it spent and no retry or fallback;
   - the director's turn ends as soon as any call, its own or a seat's, finds the server away, and the play pauses (D47).
2. **A run stopped by hand wasn't published as `push` says.** SIGINT skipped the end-of-run step. So `push: always` didn't push, and `push: approved` didn't print the `git push` command. Now an unfinished run is published as the spec's table says, however it stopped.
3. **A failed push showed git's advice, not the error.** The log kept git's last line of output, "and the repository exists.". It now keeps git's first `fatal:` or `error:` line.
4. **The director didn't wait for a remote verifier seat.** The first two-machine release-notes attempt started without `checker-remote`, and spent 40 minutes on verdicts that couldn't pass. Now the start waits, within `cast_timeout`, for every verifier seat a verifier `runs_on`, as it waits for a part's minimum seats. If one never joins, the play stops as `uncastable` before the director's first turn. Alessio agreed to this.
5. **A refusal listed the same path several times.** A path a seat may both read and write appeared once per list: "it may read: vision.md, backlog/, spec/, tests/, tests/, tests/". Each path now appears once.

Not changed:

- **The director's total input** stays around 100k tokens per kata (above).
- **The director names seats that don't exist.** It sometimes invents seat names, or cues a part by a seat it hasn't cast. Each time the rules refuse, list the real seats and parts, and the next call is right.

## Timing

- **Cloud runs:** about a minute for the kata, half a minute for release notes.
- **Local runs:** varied with the model server.
  - The kata took 553 s to 2564 s when it finished.
  - Release notes took 112–622 s.
  - The model server was slow during the first batch (see "The slow local runs").
- **Two-machine runs:** they ran on their own, not overlapping any other run. They took 775 s for the kata and 113 s for release notes.
