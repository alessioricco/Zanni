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
| `models` | list of model entries, at least one | yes | — | the actor | The models this actor runs, in order (D11). |
| `credentials` | map of name → value | no | none | the actor, and `zanni` | This instance's credentials ([below](#credentials)). |
| `state_dir` | path | no | `~/.zanni/actors/<name>` | the actor | Where the actor keeps its working memory and state. It is discarded or kept by the actor; the play's shared state lives on the stage. |

## Where the actor joins

`play` takes one of three forms (D30):

| Value | Recognised by | What the actor does |
|---|---|---|
| A director | an `http://` or `https://` URL not ending in `.yaml` or `.yml` | Fetches the director's card from `/.well-known/agent-card.json` under that URL, and joins. |
| A play file | a local path to a play file, or an `http(s)` URL ending in `.yaml` or `.yml` | Reads the play's `director`, and joins it. |
| A rehearsal | a local path to a [rehearsal](rehearsal.md) | Runs it, with a director started for it on this machine (D29). |

- **Before joining:** the actor prints the play and script named on the director's card. It refuses a director whose card doesn't carry the [casting extension](casting-extension.md) at a version it speaks, and sends it nothing.
- **Joining:** the actor presents `ZANNI_JOIN_TOKEN` from its `credentials` (D24).
- **The run:** the actor follows its seat's cues until it is released.
- **Exit codes:** `zanni` exits with:
  - 0 when the seat is released with `done`;
  - 1 when it's released for any other reason;
  - 2 when the join is refused or nothing could start.

  For a rehearsal, the codes are the rehearsal's own (D28).
- **Not yet:** a play file with no `director` means "this machine": the director starts those seats itself, which comes with milestone 4.

## The actor's log

Every actor keeps its own log, on its own machine, whether its director is local or remote (D32). The log is JSON Lines, in the play log's format (D18), at `<state_dir>/plays/<play>/<run-id>/log.jsonl`, one folder per run (a refused join has no seat); for a rehearsal, it is `actor-log.jsonl` in the run folder.

| Event | Fields | When |
|---|---|---|
| `joined` | `director`, `play`, `script`, `seat`, `part`, `permissions`, `expires_at` | The actor is cast. Tokens are never logged. |
| `join-refused` | `director`, `reason`, `message` | The director refuses the actor. |
| `cue` | `seat`, `scene`, `cue` | A cue arrives. |
| `fallback` | `seat`, `model`, `reason`, `detail` | A model failed, and the actor moved on (D20). |
| `report` | `seat`, `cue`, `outcome`, `summary`, `changes` | The actor sends its report. |
| `cost` | `seat`, `model`, `amount` | The cue's spend, `null` when unknown (D7). |
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
  - every `${NAME}` in the role's `mcp.json` is looked up first in `credentials`, then in the environment. The same role can thus run as two actors on one machine, one with a GitHub token and one with an SSH key, without either seeing the other's.
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
