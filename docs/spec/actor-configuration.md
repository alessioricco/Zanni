# Actor configuration

An actor configuration is one actor instance's own file. A zanni is an empty shell; this file tells it which role to play, which play to join, which models to run and which credentials to use. It holds what is specific to this instance, never the role's capabilities (D14). It stays on the actor's machine and never goes in a repository.

```yaml
# ~/zanni/gpu-coder.yaml
name: gpu-coder
role: github.com/zanni-roles/coder@1.0.0
play: https://example.com/plays/habit-tracker/play.yaml
models:
  - provider: ollama
    model: qwen3-coder:30b
    base_url: ${OLLAMA_BASE_URL}
    price: { input: 0, output: 0 }
  - provider: anthropic
    model: claude-sonnet-5-5
    credential: ANTHROPIC_API_KEY
credentials:
  ANTHROPIC_API_KEY: sk-ant-…              # stored here: the file must be private and untracked
  GITHUB_TOKEN: ${GITHUB_TOKEN}            # or taken from the environment
  ZANNI_JOIN_TOKEN: ${ZANNI_JOIN_TOKEN}    # presented when joining the play
```

It is recognised by having both `role` and `play`, and it is the file passed to `zanni` to start an actor. Several actors on one machine each have their own configuration file, with their own models and credentials.

## Fields

| Field | Type | Required | Default | Enforced by | Meaning |
|---|---|---|---|---|---|
| `name` | text | no | none | the actor | This instance's name, used in the log and in summaries. |
| `role` | package reference | yes | — | the director, at casting | The role this actor plays. The director casts the actor only into a part whose cast entry names this role. |
| `play` | URL or path | yes | — | the actor | Where to join: a director's URL, a play file, or a local [rehearsal](rehearsal.md) ([below](#where-the-actor-joins)). The actor decides which plays and directors it is willing to join. |
| `models` | list of model entries, at least one | yes, except for a [verifier seat](#verifier-seats) | — | the actor | The models this actor runs, in order (D11). A verifier seat runs no model, and has none. |
| `credentials` | map of name → value | no | none | the actor, and `zanni` | This instance's credentials ([below](#credentials)). |
| `state_dir` | path | no | `~/.zanni/actors/<name>` | the actor | Where the actor keeps its working memory and state. It is discarded or kept by the actor; the play's shared state lives on the stage. |
| `tools` | map of a tool's name → [binding](#tools-the-actor-brings) | no | the role's `mcp.json` | the actor, and `zanni` | Servers this actor brings for tools its role needs, such as its own coding engine (D53). |
| `workspace.commands` | list of command names | no | none | the actor | The commands a [workspace](#the-workspace) may run on this machine (D52). |
| `seats` | map of part → list of actor configuration files | no | none | the director | Only in a [director's configuration](#a-directors-configuration): the local seats it starts. |
| `verifier_seats` | `{ local, remote }` | no | none | the director | Only in a director's configuration: the [verifier seats](#verifier-seats) it trusts. |

## Tools the actor brings

An actor brings its own tools as it brings its own models (D53). A role names the tools it needs in `needs.tools`, and its `mcp.json` gives a default server for each; the actor's configuration may replace any of them with a server of its own, such as its favourite coding engine, run on its own key:

```yaml
tools:
  coding-engine:
    command: some-engine            # stands for any MCP server that works in a folder
    args: [mcp, --folder, "${ZANNI_WORKSPACE}"]
    env: { ENGINE_API_KEY: "${ENGINE_API_KEY}" }
    price: { per_call: 0 }          # what the play is charged per call: here, nothing
credentials:
  ENGINE_API_KEY: ${ENGINE_API_KEY}
```

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `command`, `args`, `env` | as in `mcp.json` | `command` or `url` | — | A server the actor starts. |
| `url`, `headers` | as in `mcp.json` | `command` or `url` | — | A server the actor reaches over HTTP. |
| `price.per_call` | number, at least 0, in USD | no | none | What the play is charged for each call to this tool. Without it, the tool's cost is unknown, never zero (D7). |

- **Only what the role asks for:** each name must be one of the role's `needs.tools`; an actor can't add a tool its role didn't ask for. `zanni` checks it when the role is a local folder, and the actor before it starts.
- **Credentials:** every `${NAME}` is looked up first in `credentials`, then in the environment. A secret-looking `env` or `headers` value must be such a reference, never a value.
- **`${ZANNI_WORKSPACE}`:** the folder of the seat's [workspace](#the-workspace) for the current cue. A tool that works on files works there; its changes reach the stage only through the workspace.
- **Cost:** each cue's reported cost adds `price.per_call` for each call to the tool, beside its models' cost (D39). Under a budget, every bound tool needs a price, or the actor is refused at join (`unpriced`).
- **Trust:** the director believes the cost an actor reports, as it believes a model's (D39). The real cap on a key is its owner's, such as a provider's spending limit.

## The workspace

A role whose `mcp.json` names `zanni:workspace` as a server's `command` gets a workspace: a local folder holding a copy of the stage, for an engine that works on real files (D52).

1. **At the start of each cue,** the actor fills a fresh folder with every stage file the seat may read.
2. **During the cue,** the role's model works in it, with the workspace's tools: `read_file`, `write_file`, `list_files` and `run`; or a tool the actor brings works in it ([above](#tools-the-actor-brings)).
3. **At the end of the cue,** before reporting, and only when the cue ends done, the actor sends what changed to the stage, as writes and deletes the director checks against the cue's paths. A change outside them is refused, and the director lists the refusals in the report; the stage is unchanged by them. A cue that fails, or stops at its budget, sends nothing.

- **What is sent:** text files only, and none that the `.gitignore` at the workspace's root ignores, such as build output or installed packages: the project's own file decides, as git would. A stage file that isn't text stays on the stage untouched.

- **`run`:** runs a command in the folder, on this machine, within a timeout, and returns its exit code and output. Only commands named in `workspace.commands` may run, by their bare name, such as `[uv, pytest]` or `[npm, node]`; with none listed, `run` refuses every command. What runs on a machine is its owner's decision, not the role's or the director's. The command's environment is the actor's, without any variable whose name looks like a secret, such as `ANTHROPIC_API_KEY` or `ZANNI_JOIN_TOKEN`. What a command leaves running, such as the app it started for a later call to probe, is stopped when the cue ends, with everything in the command's process group; a call abandoned midway stops its command at once. The workspace isn't a sandbox: a command runs with the permissions of the actor's process.
- **What it decides:** nothing on the director's side. Verifiers decide "done" (D45).
- **A lost seat:** the work of a cue that never reached its end isn't on the stage; the director resends the cue to the next seat (D36).

## Where the actor joins

`play` takes one of three forms (D30):

| Value | Recognised by | What the actor does |
|---|---|---|
| A director | an `http://` or `https://` URL not ending in `.yaml` or `.yml` | Fetches the director's card from `/.well-known/agent-card.json` under that URL, and joins. |
| A play file | a local path to a play file, or an `http(s)` URL ending in `.yaml` or `.yml` | Reads the play's `director`, and joins it. |
| A rehearsal | a local path to a [rehearsal](rehearsal.md) | Runs it, with a director started for it on this machine (D29). |

- **Before joining:** the actor prints the play and script named on the director's card. It refuses a director whose card doesn't carry the [casting extension](casting-extension.md) at a version it speaks, and sends it nothing.
- **Joining:** the actor presents `ZANNI_JOIN_TOKEN` from its `credentials`, or else from its environment (D24, D36). It also says whether every one of its models has a price (`pricing`): a play with a budget refuses an actor whose models aren't all priced (D39).
- **Overriding `play`:** `zanni <configuration> --play <URL or file>` joins another play or director than the file says. A director uses it to start its local seats (D36).
- **A cue's budget:** when a cue carries a budget, the actor checks its spend after each model response, and stops at it, reporting `over-budget` (D39).
- **The run:** the actor follows its seat's cues until it is released.
- **Exit codes:** `zanni` exits with:
  - 0 when the seat is released with `done`;
  - 1 when it's released for any other reason;
  - 2 when the join is refused or nothing could start.

  For a rehearsal, the codes are the rehearsal's own (D28).
- **A play file with no `director`** means the play runs on this machine: start it with `zanni play.yaml`, and its director starts the local seats it lists (D36).

## A director's configuration

The director is an actor too: its configuration is an actor configuration whose `role` is `zanni:director`, Zanni's built-in director role (D34). It holds the director's own models and credentials; a play never chooses models.

```yaml
# plays/slug-kata/director.yaml
name: director
role: zanni:director
play: ./play.yaml
models:
  - { provider: anthropic, model: claude-haiku-5-5 }
credentials:
  ZANNI_JOIN_TOKEN: ${ZANNI_JOIN_TOKEN}     # the play's join token, which actors present
  ZANNI_OWNER_TOKEN: ${ZANNI_OWNER_TOKEN}   # the play's owner token, for `zanni gate` (D38)
seats:                                      # local seats, one actor configuration each (D36)
  tester: [./tester-1.yaml]
  coder: [./coder-1.yaml, ./coder-2.yaml]
verifier_seats:                             # optional: where verifiers may run, besides here (D45)
  local: [./checker.yaml]                   # started by the director
  remote: [ci-box]                          # joins from elsewhere, with ZANNI_VERIFIER_TOKEN
```

- **`role`:** `zanni:director`. Zanni's built-in roles are `zanni:director` and `zanni:verifier` ([below](#verifier-seats)); any other `zanni:` name is refused.
- **`play`:** a local play file. `zanni director.yaml` runs it, like `zanni play.yaml`.
- **Where `zanni play.yaml` finds it:** `--director <file>`, or else `director.yaml` beside the play file. Nowhere else, because its tokens belong to one play. A configuration whose `play` names another play is refused.
- **`models`:** the director's own, in order with fallback (D27). Under a budget, each must have a price.
- **`credentials`:** `ZANNI_JOIN_TOKEN` and `ZANNI_OWNER_TOKEN`, one of each per play, plus the models' keys, under the same [safeguards](#safeguards). Also, when needed:
  - `ZANNI_STAGE_TOKEN`: the director's token for an `mcp` stage (D47);
  - `ZANNI_VERIFIER_TOKEN`: the token verifier seats present (D45). Required when `verifier_seats.remote` lists any; for local verifier seats only, the director makes one for the run when it's absent.
- **`seats`:** for each part, the actor configurations the director starts as local seats, one file per seat. A part the play casts with `host: local` must have at least one. The director reads only each file's `name` and `role`: the role must be the one the play casts for that part (the same remote reference, or the same local folder), and the names must be unique. Each local seat resolves its own credentials; the director never holds them.

- **`verifier_seats`:** where the play's verifiers may run besides the director's machine ([below](#verifier-seats)). `local` lists configuration files the director starts, as for `seats`; `remote` lists the names of verifier seats that join from elsewhere. Names must be unique.

## Verifier seats

A verifier seat runs a play's verifiers somewhere other than the director's machine, such as in a container or on a machine with the right tools (D45). It is a zanni with Zanni's built-in role `zanni:verifier`: it runs no model, and decides nothing. The director sends it a verifier's command in `zanni.verify`; it pulls a snapshot of the stage over MCP, with read-only access to the whole stage, runs the command there within its timeout, and answers `zanni.verdict` with the exit code and the end of the output ([Casting extension](casting-extension.md#zanniverify-and-zanniverdict)).

```yaml
# ci-box.yaml, on the machine that runs the checks
name: ci-box
role: zanni:verifier
play: http://director.example.com:8765
credentials:
  ZANNI_VERIFIER_TOKEN: ${ZANNI_VERIFIER_TOKEN}
```

- **No models:** a verifier seat's configuration has no `models`.
- **Trust:** the director believes the exit code a verifier seat reports, so it accepts only the verifier seats its own configuration lists in `verifier_seats`, each presenting `ZANNI_VERIFIER_TOKEN` in place of the join token. A seat that joins with the join token can never run a verifier; one whose name isn't listed is refused with `not-authorised`.
- **Exit codes:** as an actor's.

## The actor's log

Every actor keeps its own log, on its own machine, whether its director is local or remote (D32). The log is JSON Lines, in the play log's format (D18), at `<state_dir>/plays/<play>/<run-id>/log.jsonl`, one folder per run (a refused join has no seat); for a rehearsal, it is `actor-log.jsonl` in the run folder.

| Event | Fields | When |
|---|---|---|
| `joined` | `director`, `play`, `script`, `seat`, `part`, `permissions`, `expires_at` | The actor is cast. Tokens are never logged. |
| `join-refused` | `director`, `reason`, `message` | The director refuses the actor. |
| `cue` | `seat`, `scene`, `cue` | A cue arrives. |
| `fallback` | `seat`, `model`, `reason`, `detail` | A model failed, and the actor moved on (D20). |
| `report` | `seat`, `cue`, `outcome`, `summary`, `changes` | The actor sends its report. |
| `cost` | `seat`, `model`, `amount`, `input_tokens`, `output_tokens`, `tool_calls` | The cue's spend, `null` when unknown (D7), its tokens, and the calls to tools the actor brings (D53). |
| `released` | `seat`, `reason` | The seat ends. |

The director keeps the play's log; neither log depends on the other.

## Package references

Roles and scripts are both referenced as packages, in one of two ways:

- **A remote package:** `host/owner/name@version`, such as `github.com/someone/tester@1.4.0`, or `host/owner/repo/path/to/role@version` for one in a subfolder. The version is required, and resolves to a git tag ([Role package: versions](role-package.md#versions)). A play's lockfile pins it to a commit.
- **A local folder:** a path with no host, such as `roles/tester` or `./roles/tester`.

## Models

The actor uses the first model in `models`. It moves to the next one when the current one fails for one of the entry's `fall_back_on` reasons. When the last one fails, the actor reports the failure to the director, which may recast the seat.

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `provider` | `anthropic`, `openai`, `google`, `ollama`, or `openai-compatible` | yes | — | How the model is reached. `openai-compatible` covers any server with an OpenAI-compatible API, such as LM Studio, llama.cpp or vLLM. |
| `model` | text | yes | — | The model's name at that provider, such as `claude-sonnet-5-5` or `qwen3.8:27b`. |
| `base_url` | URL or `${VAR}` | for `openai-compatible` | the provider's own | Where the model is served, for local or self-hosted models. |
| `credential` | a name in `credentials` | no | the provider's usual environment variable, such as `ANTHROPIC_API_KEY` | The credential used to call this model. |
| `tool_format` | `native` or `text` | no | `native` | `text` turns on the opt-in text tool format, for models without native tool calling (D5). |
| `price` | `{ input, output }`, USD per million tokens, at least 0 | no | published prices, if any | The model's price, for models published prices don't cover, such as local ones. Without a price, a model's cost is unknown, never zero (D7). |
| `fall_back_on` | list of reasons | no | `[error, timeout, rate-limit, context]` | When to move to the next model. |
| `max_output` | whole number, at least 1 | no | the provider's own | The most tokens one model response may hold, so a model stuck repeating itself stops early (D61). |

### Reasons to fall back

| Reason | Means |
|---|---|
| `error` | The provider returned an error, or couldn't be reached. |
| `timeout` | The model didn't answer in time. |
| `rate-limit` | The provider refused the request because of a rate or quota limit. |
| `context` | The request didn't fit in the model's context window. |
| `refusal` | The model refused the task. Not in the default list, because a refusal can be the right answer; add it only when another model should try. |

## Credentials

`credentials` maps names to values, like an addressable `.env` for this one actor (D15).

- **Names:** letters, digits and underscores, such as `ANTHROPIC_API_KEY`, `GITHUB_TOKEN` or `SSH_KEY_PATH`.
- **Values:** a value is either stored in the file, or a reference `${VAR}` (or `${VAR:-default}`) read from the environment when the actor starts.
- **Who uses them:**
  - a model entry's `credential` names the one it uses;
  - every `${NAME}` in the role's `mcp.json`, and in the configuration's own `tools`, is looked up first in `credentials`, then in the environment. The same role can thus run as two actors on one machine, one with a GitHub token and one with an SSH key, without either seeing the other's.
- **Elsewhere in the file:** secret-looking keys anywhere else in the file are rejected, with a pointer to `credentials`.

### Safeguards

When `credentials` stores any value (not a `${VAR}` reference), `zanni` refuses the file:

- **if other users can read it**, meaning its mode is looser than `600`. The message gives the `chmod` to run. SSH does the same with private keys.
- **if git tracks it**, wherever it is. The message says how to untrack it.

These checks are enforced by `zanni`, and by the actor before it starts. On top of them:

- **Values are never shown:** a credential's value is never printed, logged or sent to the director. Summaries show each name and where its value comes from, and error messages never show a value.
- **References are not protected:** a configuration whose credentials are all `${VAR}` references holds no secret, so it can be shared or committed. The repository's example, `examples/tester.yaml`, is one.

**Not in the first version:** secrets management for actors running on cloud services.

## Not in the first version

- **A shared list of models:** the vision's `models_list.yaml` was a list of models, with ratings and fallback ladders, to share across machines. Each actor configuration now holds its own ordered list (D11), which is all the first version needs. A shared list can come later as a file a configuration includes.
