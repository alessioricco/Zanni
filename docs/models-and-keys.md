# Models and keys

> **Status:** an actor runs its models in a [rehearsal](spec/rehearsal.md) or in a seat it joined over A2A, and a play's director runs its own. Recorded runs are in [docs/runs/](runs/): [milestone 2](runs/milestone-2.md), [milestone 3](runs/milestone-3.md) and [milestone 4](runs/milestone-4.md).

## Each actor brings its own models and keys

The model is the actor's choice, set in its own configuration (D11). Neither the script nor the play chooses it. A role can only hint, through `model.needs` and `suggested`.

An actor configuration lists its models in order. The first is used, and the next when one fails, which is also how an actor escalates from a local model to a cloud one. The configuration also holds this instance's credentials (D15):

- API keys for its models;
- tokens or key paths for its tools, such as GitHub or an SSH terminal.

Two actors on one machine have two configuration files, each with its own models and access:

```yaml
# ~/zanni/gpu-coder.yaml (chmod 600, not in any repository)
name: gpu-coder
role: github.com/zanni-roles/coder@1.0.0
play: https://example.com/plays/habit-tracker/play.yaml
models:
  - { provider: ollama, model: qwen3-coder:30b, base_url: "${OLLAMA_BASE_URL}", price: { input: 0, output: 0 } }
  - { provider: anthropic, model: claude-sonnet-5-5, credential: ANTHROPIC_API_KEY }
credentials:
  ANTHROPIC_API_KEY: sk-ant-…
  GITHUB_TOKEN: ghp_…
```

- **Order:** the first model is used; the next is tried when one fails with an error, a timeout, a rate limit, or a request too long for its context. A refusal moves to the next model only if you add `refusal` to `fall_back_on`.
- **Other servers:** `openai-compatible` reaches any OpenAI-compatible server, with its `base_url`.
- **Where credentials go:** a model entry's `credential` names the credential it uses. The role's `mcp.json` picks up `${GITHUB_TOKEN}` and the like from `credentials` first, then from the environment.

Every field is in the [actor configuration spec](spec/actor-configuration.md).

## The director's models and keys

The director is an actor too, and Zanni never picks its model: the director runs on the models its own configuration lists, `director.yaml` beside the play (D34). Use any model with tool calling, local or cloud, in order with fallback. When every one of them fails, the play pauses until its owner resumes it with `zanni gate <play> resume` (D33).

```yaml
models:
  - provider: anthropic
    model: claude-haiku-5-5            # stands for a cloud model with tool calling
  - provider: ollama
    model: qwen3.8:27b                 # stands for a local model with tool calling
    base_url: ${OLLAMA_BASE_URL}
    price: { input: 0, output: 0 }
credentials:
  ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
  ZANNI_JOIN_TOKEN: ${ZANNI_JOIN_TOKEN}
  ZANNI_OWNER_TOKEN: ${ZANNI_OWNER_TOKEN}
```

- **Its keys stay its own:** the director never holds an actor's keys. Local seats resolve their own credentials, from their own configurations (D36).
- **The owner token:** `ZANNI_OWNER_TOKEN`, one per play, decides gates. The owner sets the same value in the environment where they run `zanni gate`; it is never a flag, and never logged (D38).

## The join token

An actor joins a director with the play's join token (D24):

- **On the actor's side:** it goes in the actor configuration's `credentials`, as `ZANNI_JOIN_TOKEN`, either stored or as `${ZANNI_JOIN_TOKEN}` from the environment.
- **On the director's side:** a play's director takes it from its configuration's `credentials` (D34); `zanni <rehearsal> --serve` reads it from `ZANNI_JOIN_TOKEN` in its environment.
- **Local seats:** the director gives it to the seats it starts, in their environment; an actor reads `ZANNI_JOIN_TOKEN` from its `credentials`, or else from its environment (D36).
- **Who sees it:** it travels only in the `Authorization` header of the join. After that, the actor uses the seat's own tokens, which the director gives it and revokes at release. No token is ever logged.
- **On untrusted networks:** `--serve` speaks plain HTTP, so put it behind a TLS proxy (`TODO.md`).
- **A rehearsal run from an actor configuration needs no join token:** its director runs in the same process, and makes one up for the run.

## Secrets: only in actor configurations

- **Roles, scripts and plays never hold secrets.** They are shared and published, so `zanni` rejects any key in them that looks like a secret (`api_key`, `token`, `password`, `client_secret`, …).
- **An actor configuration may hold its own credentials.** It is an instance file, not project code, and never goes in a repository. `zanni` protects it:
  - it refuses a configuration that other users can read, and gives the `chmod` to run;
  - it refuses one that git tracks;
  - it never prints, logs or sends credentials to the director.
- **A credential may come from the environment instead**, as `${VAR}`. This is useful in CI. `zanni` reads the environment, not a `.env` file. If your keys live in a `.env`, load it into your shell first: `set -a; . ./.env; set +a`.

## Any model, local or cloud

No role, script or play depends on a particular model or vendor:

- **Roles state what they need:** tool calling, a context size, a tier such as `judgement`. A role may suggest a default.
- **Local models aren't tied to one server.** They are reached through any OpenAI-compatible endpoint: Ollama, LM Studio, llama.cpp, vLLM and others. You don't need a local server if you use a cloud model, and you don't need a cloud key if you only use local models.
- **Models without native tool calling** can use an opt-in text-based tool format: `tool_format: text` in the model entry. It is opt-in per model, so models that call tools natively are never affected (D5). For an Ollama model, `zanni` asks the server what the model can do before running. If the role needs tools and the model can't call them, `zanni` refuses to start and suggests `tool_format: text`.
- **Google models** need an optional extra: `uv sync --extra google`.
- **Quality is checked, not assumed.** The director can't see which model an actor used, so verifiers decide whether work is done.

## Cost

- **Priced models:** a seat's cost comes from published prices, for the cloud models those prices cover.
- **Local models:** the actor's configuration can declare a price, which can be 0 for its own hardware.
- **Unknown cost is never counted as zero.** The director treats a seat with an unknown cost as unsafe for the play's budget (D7).
- **Under a budget, every model needs a price** (D39): an actor whose models aren't all priced is refused when it joins (`unpriced`), and a director whose models aren't all priced doesn't start. Add `price:` to a local model's entry, even `{ input: 0, output: 0 }`.
- **A cue's budget:** each cue carries a budget, and the actor stops its work when the cue's spend reaches it, reporting `over-budget`.
- **What a budget can't do:** costs are what actors report. The real cap on a key is its owner's, such as a provider's spending limit.
