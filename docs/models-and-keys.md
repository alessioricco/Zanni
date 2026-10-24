# Models and keys

> **Status:** an actor runs its models today, in a [rehearsal](spec/rehearsal.md) or in a seat it joined over A2A. Recorded runs are in [docs/runs/milestone-2.md](runs/milestone-2.md) and [docs/runs/milestone-3.md](runs/milestone-3.md).

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

## The join token

An actor joins a director with the play's join token (D24):

- **On the actor's side:** it goes in the actor configuration's `credentials`, as `ZANNI_JOIN_TOKEN`, either stored or as `${ZANNI_JOIN_TOKEN}` from the environment.
- **On the director's side:** `zanni <rehearsal> --serve` reads it from `ZANNI_JOIN_TOKEN` in its environment.
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
