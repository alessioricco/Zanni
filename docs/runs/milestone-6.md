# Milestone 6: recorded runs

Run on 2026-10-25 and 2026-10-26. Every result below ran; nothing is projected. Claims about milestone 6 in the docs point here.

## What ran

One script, `examples/scripts/software-team/` 2.0.0, performed by two plays that differ only in the project's stack (D56):

- **`software-mini-python`:** the vision is "a unit converter web page"; the stage starts with `vision.md`, `pyproject.toml` and `.gitignore`, and the play's verifier commands use `uv` and `pytest`.
- **`software-mini-node`:** the same vision, with `package.json` and `node --test`.

Both use the same six roles (`examples/roles/`: product-owner, architect, ui-designer, tester, developer-lead, coder), the same seats, and a git stage made by the play's `make-remote.py`. One round of the script is nine scenes: plan, backlog review, specify, spec review, tests, build, check, explore, release. The reviews are D59's loop: each reviewer writes its own file under `reviews/`, and the author revises once and answers. The `plan` gate holds back `spec/`, `tests/`, `tasks/` and `app/` until it is approved (D62); the `release` gate ends the round.

Each run used a fresh copy of `examples/`, with new join and owner tokens, kept out of every log. A driver script played the owner: it started the director with its standard input closed, decided each gate with `zanni gate <play> approve` (or `reject`, or `approve --another-round`, where the run needed it), and stopped the director after 3 hours if it hadn't stopped by then. The configuration decided every model; the driver only wrote each copy's `models:` before starting.

| Layout | The director | The planning parts (product-owner, architect, ui-designer) | The rest (tester, developer-lead, coder) |
|---|---|---|---|
| **Cloud** | `claude-haiku-5-5` | `claude-haiku-5-5` | `claude-haiku-5-5` |
| **Mixed** | `claude-haiku-5-5` | `claude-sonnet-5-5` | `qwen3.8:27b`, on a local model server |
| **Local** | `qwen3.8:27b` | `qwen3.8:27b` | `qwen3.8:27b` |

Every seat ran on the director's machine, except in the two-machine run (below). Workspaces ran `uv` (and `npm`, `node` for the Node play), as each actor configuration's `workspace.commands` allowed.

| Component | Version |
|---|---|
| zanni | `software-script` at `c5cac8d` (item 8), plus the fixes in item 9's commit, described below |
| Python | 3.14.4 on the director's machine |
| a2a-sdk | 1.2.3 |
| mcp | 2.3.0 |
| fastmcp-slim | 4.1.3 |
| pydantic-ai-slim | 2.60.0 |
| genai-prices | 0.1.13 |
| git | 2.46.1 |
| uv | 0.10.4 |
| Node.js | 22.22.0, npm 11.11.0 |
| Ollama server | 0.40.6 on the local model server |
| Claude Code | 2.1.310, as the coder's own engine in one run (`claude mcp serve`) |
| `qwen3.8:27b` | native tool calling, `price: { input: 0, output: 0 }` in each configuration |
| `claude-haiku-5-5`, `claude-sonnet-5-5` | Anthropic API, priced by genai-prices |

## Results

As in milestone 5:
- **Time** runs from `run-started` to `run-stopped` in the play's log.
- **Tokens** are input / output, summed over the director's turns or over a seat's cues.
- **Verdicts** count every verifier run, so `new-tests-fail` run after the code exists would count as failed.
- **Refused** counts the writes the stage's permission layer refused, from the `report` events (D54).

### Cloud: one round of the Python play

| Run | Result | Verdicts passed | Time (s) | Director: turns, tokens, cost | Seats: cues, tokens, cost | Total | Refused | Exit |
|---|---|---|---|---|---|---|---|---|
| a | ✅ done | 8 / 8 | 668 | 14, 284666 / 15313, $0.0195060 | architect 3, 89526 / 24608, $0.0212566; coder 1, 68773 / 7729, $0.0107418; developer-lead 2, 65459 / 6615, $0.0098534; product-owner 3, 75726 / 18786, $0.0169656; tester 4, 667501 / 55596, $0.0945481; ui-designer 1, 12580 / 2061, $0.0022885 | $0.1751600 | 23 | 0 |
| b | ✅ done | 9 / 9 | 533 | 14, 244693 / 13493, $0.0165256 | architect 3, 132001 / 26103, $0.0262516; coder 1, 175534 / 6689, $0.0208979; developer-lead 2, 62614 / 6710, $0.0096164; product-owner 4, 75190 / 17704, $0.0163710; tester 4, 466711 / 37359, $0.0653506 | $0.1550131 | 3 | 0 |
| c | ✅ done | 8 / 8 | 734 | 16, 271410 / 12540, $0.0170886 | architect 3, 78728 / 27063, $0.0214043; coder 2, 88346 / 8069, $0.0128691; developer-lead 2, 40558 / 6668, $0.0073898; product-owner 3, 46248 / 12018, $0.0106338; tester 4, 500424 / 41633, $0.0708589 | $0.1402445 | 10 | 0 |
| d | ✅ done | 6 / 6 | 525 | 14, 184496 / 11257, $0.0122444 | architect 3, 100982 / 21877, $0.0210367; coder 1, 81684 / 6792, $0.0115644; developer-lead 2, 74677 / 8605, $0.0117702; product-owner 3, 47944 / 12333, $0.0109609; tester 4, 322209 / 36710, $0.0505759 | $0.1181525 | 3 | 0 |

The ui-designer part is optional in the script. Its local seat joined in every run, but of these four, the director gave it a cue only in a.

### Once each

| Run | What it showed | Result | Verdicts passed | Time (s) | Director's cost | Total | Refused | Exit |
|---|---|---|---|---|---|---|---|---|
| Caching off | H's "before": the same run with the director's prompt caching off | ✅ done | 10 / 10 | 633 | $0.0347917 | $0.1363893 | 3 | 0 |
| Node | E: the Node play, same script, roles and seats | ✅ done | 10 / 10 | 539 | $0.0157686 | $0.1341207 | 0 | 0 |
| Two coders | C: two coder seats, each on a workstream of its own | ✅ done | 11 / 12 | 457 | $0.0218797 | $0.1219550 | 5 | 0 |
| Plan rejected | the owner rejected the first plan, with a note | ✅ done | 8 / 8 | 516 | $0.0155884 | $0.1417572 | 3 | 0 |
| Another round | the owner granted another round at the `release` gate (D60) | ✅ done, in round 2 | 14 / 14 | 1039 | $0.0418430 | $0.3419707 | 0 | 0 |
| Continued | a new run from where "another round" ended, with `--continue` (D60) | ✅ done, as round 3 | 10 / 10 | 551 | $0.0168299 | $0.1596155 | 0 | 0 |
| Own engine | the coder brought Claude Code as its workspace (D53) | ✅ done | 8 / 8 | 615 | $0.0165627 | $0.2014946 | 0 | 0 |

All on `claude-haiku-5-5`, the Python play unless noted.

### Mixed and local: the same play, on a local model

| Run | Result | Verdicts passed | Time (s) | Director: turns, tokens, cost | Seats: cues, tokens, cost | Total | Refused | Exit |
|---|---|---|---|---|---|---|---|---|
| mixed a | `uncastable`, in scene 5 | 0 / 0 | 5510 | 8, 141822 / 7581, $0.0100907 | architect 3, 81717 / 18288, $0.346314; developer-lead 1, 26140 / 5680, $0; product-owner 2, 25933 / 7975, $0.131616; tester 3 + 1 + 1 | $0.4880207 | 0 | 1 |
| mixed b | `uncastable`, in scene 4 | 0 / 0 | 4658 | 6, 100109 / 4598, $0.0067104 | architect 2, 41076 / 8661, $0.168762; developer-lead 1, 32348 / 12273, $0; product-owner 2, 26323 / 8311, $0.135756; tester 2 + 1 + 1 | $0.3112284 | 0 | 1 |
| local a | `uncastable`, in scene 8 | 4 / 4 | 10770 | 13, 199784 / 15833, $0 | architect 3, 112362 / 22537; coder 1, 330422 / 9508; developer-lead 2, 64269 / 9683; product-owner 2, 29427 / 7362; ui-designer 1, 29762 / 3646; tester 3 + 2 + 1, one cost unknown | $0, at least | 2 | 1 |
| **mixed c**, after the fixes | ✅ done | 10 / 10 | 4652 | 14, 239066 / 11689, $0.0172599 | architect 3, 118557 / 15794, $0.395054; coder 1, 142901 / 7291, $0; developer-lead 2, 69793 / 7366, $0; product-owner 3, 41026 / 10988, $0.191932; tester 4, 834564 / 55541, $0; ui-designer 1, 12401 / 1451, $0.039312 | $0.6435579 | 0 | 0 |
| **local b**, after the fixes | `uncastable`, in scene 5 | 0 / 0 | 8491 | 9, 145884 / 14647, $0 | architect 3, 119564 / 24842; developer-lead 1, 24055 / 4380; product-owner 2, 50797 / 9557; ui-designer 1 + 1, 10432 / 815; tester 3 + 1 + 1, one cost unknown | $0, at least | 0 | 1 |

"Tester 3 + 1 + 1" is three seats in turn: the first seat's cues, then each recast seat's. Every cost on `qwen3.8:27b` is $0, as its configuration declares it.

- **The first three stopped on engine bugs,** not on the model. Each ended the same way: a tester's cue ran past its deadline, the seat was recast, and the resent cue kept the deadline that had already passed (finding 4), so each new seat was released within seconds, until the restarts were used up.
  - **Mixed a:** the tester's tests cue ran past its 60 minutes; the two recast seats lasted 7 and 8 seconds.
  - **Mixed b:** the same, one scene earlier, in the tester's spec review.
  - **Local a:** got furthest, through one verdict of each verifier, all passing. Its first tester's cue failed on the stage tool's retry limit (finding 5), and the seat was released for its unknown cost, which used one restart. In the explore scene, the director, itself on `qwen3.8:27b`, gave the second tester 15 minutes; it ran past them, and the last seat was released after 8 seconds.
- **Mixed c ran after the fixes, and reached done.** Its local tester took 26 minutes to review the spec, 23 to write the tests and 12 to explore; its local coder built the app in 6 minutes, and every verdict passed. The tester read 834564 input tokens on a model priced at nothing. The run's cost is the cloud parts': the planning parts on `claude-sonnet-5-5` ($0.63), and the director on `claude-haiku-5-5` ($0.02). It started at 07:17:32; the workspace server's last change (finding 6) was saved at 07:19:52, so the one cue whose workspace started before then, the tester's backlog review, ran the earlier version. That cue ran no command.
- **Local b ran after the fixes, and stopped `uncastable` in the tests scene, this time on the model's speed.** The resent cues got new deadlines, as they now should (finding 4), but nothing else gave the tester time:
  1. **The model's requests have a 10-minute limit.** The tester's first try at the tests ended after 30 minutes, at 10:03, with `ModelTimeoutError`: one of its model requests took longer than the OpenAI client's read timeout of 600 s, three times over (the client's default of 2 retries). The client is the one Pydantic AI uses for an OpenAI-compatible local server; Zanni sets none of these.
  2. **A failed cue's cost is unknown,** so the director released the seat under the play's budget (D7), and recast it, using one of its two restarts.
  3. **The director's own deadlines were short.** On `qwen3.8:27b`, the director gave the recast tester 20 minutes for the tests, then 20 again for the resent cue, where the director on `claude-haiku-5-5` gave every cue 60 minutes in mixed c. The last seat finished at 10:50, four minutes after its release, and its report was refused.

  The actor then crashed with a traceback while sending that late report. It is now fixed: an answer the director refuses because the seat was revoked ends the seat as `revoked`, with one line saying so (finding 8).

So in mixed c, a local model played the tester, the developer lead and the coder to done. The all-local play finished neither of its runs (3.0 and 2.4 hours); in local b, the tests scene is where a local model's long outputs met the model client's 10-minute limit.

### Two machines: the coder on a second machine

The director and five seats (on `claude-haiku-5-5`) ran on the director's machine; the coder joined from a second machine on the same network, on that machine's own local model server, with `qwen3.8:27b` and `workspace.commands: [uv]`. The play had no local seat for the coder, so only the second machine could take the part. The director listened on `0.0.0.0:8765`; the join token travelled as a file.

| Run | Result | Verdicts passed | Time (s) | Director: turns, tokens, cost | Seats: cues, tokens, cost | Total | Refused | Exit |
|---|---|---|---|---|---|---|---|---|
| two machines | ✅ done | 10 / 10 | 2544 | 15, 282036 / 15193, $0.0205205 | architect 3, 156468 / 25679, $0.0284863; coder 1, 265336 / 12503 (24 tool calls), $0, on the second machine; developer-lead 2, 70331 / 9355, $0.0117106; product-owner 3, 49958 / 12465, $0.0112283; tester 4 + 1, 132185 / 21560 and 525598 / 16844, $0.0849803; ui-designer 1, 10886 / 1821, $0.0019991 | $0.1589251 | 0 | 0 |

- **The coder worked on its own machine,** in its own workspace: it filled a folder there from the stage, built `app/__init__.py`, `app/convert.py`, `app/server.py` and `app/__main__.py` in one cue of 30 minutes, ran the tests there with `uv`, and the four files reached the stage through the director when the cue ended, checked against the cue's paths. No write was refused. The first `tests-pass` and `app-starts` passed on the director's machine, 13 seconds after its report.
- **The tester lost its seat to a port.** Two minutes into exploring the app, the tester's calls to the director began to answer `501 Unsupported method ('POST')`: the reply of Python's `http.server`, which the app is built on. The app had most likely been started on port 8765, the director's own port: on macOS, a server listening on `127.0.0.1:8765` takes that address from one listening on `0.0.0.0:8765`, so the seats on the director's machine, which reach it at `127.0.0.1`, reached the app instead. The tester's cue failed, its seat was released, and the workspace stopped the app when the cue ended (finding 6). The director recast the tester, whose resent cue found two bugs and wrote them as findings with failing tests. The coder, which reached the director by the machine's name, was never affected.
- **The tester's actor crashed** sending its report to the app; finding 8 now covers a director that can't be reached, as well as a revoked seat.
- **The coder's actor didn't end.** The director sent the coder its release at 17:21:58, had no confirmation within its 30-second wait, revoked the seat at 17:22:28, and stopped. The actor on the second machine never printed its release, and was still running some time later. The second machine shut down before we could see where it was waiting, so the cause isn't known. One possible cause fits: an actor follows its seat's task over a stream with no read timeout, and the director counts an open stream as contact, so a connection that died quietly during the coder's 30-minute cue would go unnoticed on both sides. That stays a guess until a run shows it; it is in `TODO.md`.

## What the reviews changed (J)

Every run went through both review loops: the architect and the tester reviewed the backlog, and the product owner revised it once and answered in `reviews/round-1/backlog-answers.md`; then the tester and the developer lead reviewed the spec, and the architect revised it once and answered in `spec-answers.md`. Nobody edited what they reviewed: each reviewer's cue could write only its own review file (D59).

The backlog's acceptance criteria, before and after its review, from the git stage's history:

| Run | Before the review | After the revision |
|---|---|---|
| cloud a | 17 | 22 |
| cloud b | 16 | 16, then 17 after the plan was approved (below) |
| cloud c | 10 | 11 |
| cloud d | 14 | 17 |
| caching off | 15 | 20 |
| Node | 16 | 28 |
| two coders | 10 | 17 |
| plan rejected | 11 | 12, revised again after the rejection |
| another round | 15 | 18 |
| own engine | 17 | 22 |
| mixed a | 19 | 19 |
| mixed b | 19 | 28 |
| local a | 10 | 10 |
| mixed c | 22 | 33 |
| local b | 19 | 20 |
| two machines | 13 | 18 |

The reviews added criteria in 13 of these 16 runs. Where none were added, the revision changed the existing ones instead, and the answers file listed each point as accepted, changed or declined. What the reviewers raised, in the two-coders run for example: a criterion allowing "200 or 400", so a test couldn't assert either; no named element for the result, so "1000" could match the echoed input; no rule for number format and rounding; no exact message for a missing unit. In mixed a, a reviewer caught a wrong expected value in a criterion, and the revision corrected it to 39.370079 inches (100 / 2.54, to six places).

**The plan rejected.** The owner rejected the first plan at 69 s, with "Split the first item into two smaller ones, each with its own criteria." The director cued the product owner to revise the backlog with that note, asked the gate again, and the owner approved at 100 s. The spec, tests and code came only after that: the `before_writes` gate held them back (D62).

**Findings.** The tester's explore scene wrote findings in 8 of the 10 cloud runs that started from an empty project (all but cloud c and two coders), each as `findings/<item>.md`, most with a failing test under `tests/findings/`. For example: an overflow inside a conversion (cloud b and d), a page served for a `//` path (Node), one idle connection blocking the single-threaded server (cloud a, own engine). The script leaves findings to the next round: in "another round", round 2's backlog took in the weights from the owner's note and the overflow finding from round 1.

## The stack belongs to the project (E)

The Node run used the same script, the same six roles and the same seats as the Python runs. What differed was only what the play brings:
- **the stage's own files:** `package.json` instead of `pyproject.toml`;
- **the verifiers' commands:** `npm test` (which runs `node --test`) instead of `pytest`;
- **the actors' `workspace.commands`:** `[npm, node]` instead of `[uv]`.

No role names a language. From the same instructions that produced Python in the other runs, the architect specified JavaScript modules for the project `package.json` describes, the tester wrote `node:test` files (`tests/*.test.js`), and the coder wrote `app/convert.js`, `app/page.js` and `app/server.js`. It reached done with 10 verdicts out of 10, no write refused, and two findings.

## Two coders, and nobody merges (C)

With two coder seats, the architect's spec split the code into non-overlapping modules, and the developer lead made two workstreams of them in `tasks/round-1.md`: `convert` (`app/__init__.py`, `app/convert.py`) and `web` (`app/web.py`, `app/__main__.py`). The director cued both coders at once, each with its workstream's paths in `writes` (D54).
- **No write crossed workstreams:** none of the run's 5 refused writes was a coder writing the other's paths. All 5 were `uv.lock` (finding 2).
- **A workstream couldn't see the other's work:** both workspaces were filled when the two cues started, before `app/convert.py` existed, so the `web` coder's tests couldn't import it. That coder wrote its files, said so in its report, and didn't copy the other's module in.
- **One failure, fixed by a cue:** the first `tests-pass` failed on two tests: `GET /` answered 400. The director cued the developer lead, who added a fix task for `web` to `tasks/round-1.md`, then cued the `web` coder, and the next `tests-pass` passed, with 61 tests.

Alessio's condition at ask point C holds so far: the coders didn't need the same files. But a workstream that uses another's code can't run its tests in the same round of cues; the script could order such workstreams, or have the developer lead's contract stubbed first. Branches and merges stay in `TODO.md`.

## Another round, and continuing (K)

- **Another round:** at the `release` gate, the driver approved with `--another-round` and the note "Next round: weights (grams, kilograms, pounds, ounces).". The director ran round 2 from the plan scene: a round-2 backlog with the weights and the round 1 findings, its reviews, spec, tests and code. It ended done in round 2, with `another_round` in the log. It took 1039 s and $0.34, about two rounds' worth.
- **Continued:** a new run with `zanni play.yaml --continue 20261025T211925Z`. It started from that run's stage, on a new branch descended from the earlier one, as round 3, with its own budget, cast and log. It ended done, and its branch was pushed at the end, as `push: approved` says.

## Prompt caching for the director (H): before and after

The same play and models, with the director's instructions cached (D61) and without:

| | Caching off (1 run) | Caching on (cloud a–d) |
|---|---|---|
| Director's turns | 14 | 14–16 |
| Director's input tokens | 281807 | 184496–284666 |
| Director's cost | $0.0347917 | $0.0122444–0.0195060 |
| Director's share of the run's cost | 25.5% | 10.4–12.2% |
| Run's total cost | $0.1363893 | $0.1181525–0.1751600 |

For about the same input, the director cost half as much, and its share of the run fell from a quarter to a tenth. Most of a run's cost is now the tester's: it reads the most, and runs the tests.

## A tool the actor brings (B): Claude Code as the coder's engine

Alessio agreed to one watched run on the director's machine. The coder's configuration brought its own `workspace`:

```yaml
tools:
  workspace:
    command: claude
    args: [mcp, serve]
    price: { per_call: 0 }
```

- **It worked as a workspace:** the coder's model edited files and ran the tests through Claude Code's tools, and the changes reached the stage at the end of the cue, checked against the cue's paths like any other.
- **It was priced as declared:** 8 of the coder's 23 tool calls were to the brought server, each charged $0, as its configuration said. The coder read 510728 input tokens, more than in any other run: Claude Code's tool descriptions are long.
- **It ran outside the workspace's limits:** to try the app, the coder started it through Claude Code's own shell, which `workspace.commands` doesn't govern, and two files appeared in `/tmp` (`app_out.txt`, `app_err.txt`). They were harmless; I removed them after the run, and no process was left running. A tool an actor brings is the actor's own; Zanni only charges for it. This is in `TODO.md`, under containing a workspace's commands.

## The director's tool calls the rules refused

The director acts only through tools that check the rules in code first (D33). Across the 17 runs above, its tools refused 89 calls, and none came from a gate: it never tried to cue a held-back part or path before its gate was approved.

| Refused | Why | Times |
|---|---|---|
| `cue` | a cue's budget above its share: the unreserved budget, shared among the idle seats (D39) | 59 |
| `cue` | a cue naming paths for the seat to read that its part can't read, such as `app/` and `tests/` for the product owner reviewing the round | 20 |
| `cast` | a number of coder seats outside the play's range | 5 |
| `run_verifier` | a cue that writes to the stage still pending, so the verdict would judge unfinished work | 2 |
| `cue` | a seat still working on its last cue | 2 |
| `cue` | a path for the seat to write that its part can't write (`.python-version`, for the coder) | 1 |

Every refusal reached the director as a tool's answer, and it went on: after each budget refusal, it cued again with an amount within the share (55 times straight away, 4 times after a second refusal).

## What the runs found, and what changed

Fixed in item 9's commit, each with a test:

1. **The roles that work on the project couldn't read its root files.** In cloud a, the stage refused 23 writes: build output such as `.pytest_cache/`, because the actors' workspaces lacked the project's `.gitignore`, so nothing was ignored. The architect, tester, developer lead and coder now read the whole stage (`stage_read: ["/"]`); runs after it refused only what the stage should.
2. **`uv.lock` was refused in every Python run of the first batch** (3–5 a run): the play's `.gitignore` listed it with a comment on the same line, which git reads as part of the pattern. The comment is now on its own line, and the later runs refused nothing.
3. **Verifiers and workspace commands ran in Zanni's own virtual environment.** `VIRTUAL_ENV` leaked from the director into the project's commands, and `uv run` warned on every verdict. It's now dropped from the environment of verifiers and of the workspace.
4. **A resent cue was already late.** A seat lost to its cue's deadline was recast, and the cue resent to the new seat with the same deadline, already past, so the director released the new seat within seconds, then the next. With a local seat's two restarts used up, the play stopped as `uncastable`. This stopped all three runs that had a local tester (mixed a, mixed b, local a). A resent cue now gets a new deadline, as long as the first, and the `cue` event logs each cue's deadline.
5. **A stage tool gave up after one refusal.** The stage's tools inherited Pydantic AI's default of one retry, so a model that asked twice for a path that didn't exist ended its cue with an error. They now take refusals as often as an MCP tool's (3 in a row).
6. **A workspace command could outlive its cue.** After local a had stopped, four of the local coder's `pytest` runs and the app the tester had started were still running, hours later. The four test runs had started about six minutes apart, which fits the actor giving up on a tool call after Pydantic AI's default of 300 s and the model trying again; the workspace stopped a command only at its own timeout, never when its call was abandoned. The tester's app had been started by a command that returned. Now the workspace stops a command's whole process group when its call is abandoned, and every group it started when the cue ends; and the actor waits up to 15 minutes for a tool call, longer than the workspace's own limit of 10 minutes on a command. I stopped the leftover processes by hand.
7. **An empty value's error read badly:** `""` for a required name now says "is empty; give it a value, or remove it".
8. **An answer that couldn't arrive crashed the actor.** In local b, the last tester finished its cue after the director had released the seat; in the two-machine run, a tester's report reached the app instead of the director. Each time, sending the report raised an error out of the actor as a traceback. The seat now ends as `revoked` or `lost`, with one line saying why.

Not changed, and in `TODO.md`:

- **The director had the backlog changed after the plan was approved,** in two runs (cloud b, "another round"): a later cue to the product owner wrote `backlog/round-1.md` again. `before_writes` holds paths back until its gate is approved, and no longer, so the owner approved a plan that then changed.
- **A cue that failed midway reported an unknown cost,** even on a free local model: in local a, the tester's cue ended on the stage tool's retry limit (finding 5), and in local b on a model timeout. Each time, with its cost unknown under a budget, the director released the seat, which used one of its two restarts.
- **The director chooses each cue's deadline,** and on a local model it chose short ones: 10 to 20 minutes for some cues in local a and b, where its local seats needed more. Nothing gives a deadline a floor, or fits it to the seat's models.
- **A local model's request has the client's 10-minute limit,** retried twice: in local b, one request of the tester's took longer, and the cue failed after 30 minutes. A model entry can't set its request timeout yet.
- **The director sent a cue named "placeholder"** to the coder in cloud c, before its workstream existed; the coder answered that it would do nothing. It cost a few cents' worth of tokens and changed nothing.
- **An actor on another machine that didn't end after its release,** in the two-machine run; the cause is unknown (above).
- **An app started in a workspace can take the director's address.** In the two-machine run, an app the tester started took port 8765 on `127.0.0.1` from the director listening on `0.0.0.0`, and a seat lost its cue. A workspace's commands share the machine's network with the director and the seats on it.
- **A workspace isn't a sandbox:** a command the actor's owner allows, such as `uv run python`, can still write outside the folder; and a tool an actor brings runs with its own permissions.

## Totals

| | Runs | Done | Time | Tokens, input / output | Spend |
|---|---|---|---|---|---|
| Cloud, `claude-haiku-5-5` | 11 | 11 | 6810 s (1.9 h) | 13291537 / 1329371 | $1.8258731 |
| Two machines | 1 | 1 | 2544 s (0.7 h) | 1492798 / 115420 | $0.1589251 |
| Mixed | 3 | 1 | 14820 s (4.1 h) | 1976421 / 190871 | $1.4428070 |
| Local, `qwen3.8:27b` | 2 | 0 | 19261 s (5.4 h) | 1337521 / 156744 | $0, with two cues' costs unknown |
| **All** | 17 | 13 | 43435 s (12.1 h) | 18098277 / 1792406 | **$3.4276052** |

Cloud is the four runs of the first table and the seven run once each. Every cost is what the actors and the director reported, priced by genai-prices for the Anthropic models; the $10 cap set at ask point I was never near, and no run passed its own $2.

## Timing

- **Cloud runs:** 457–734 s for one round; 1039 s for two.
- **Two machines:** 2544 s, 30 minutes of it the remote coder's one cue.
- **Mixed c:** 4652 s for one round; 61 minutes of it were the local tester's cues (spec review 26 minutes, tests 23, exploring 12).
- **Local:** on `qwen3.8:27b`, the product owner's first backlog took 3 to 8 minutes, a spec review 8 to 13 minutes, and the coder's build 35 minutes in local a. Neither local run finished a round.
