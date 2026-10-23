# Models and keys

> **Status:** nothing in Zanni calls a model yet. The rule about secrets in shared files holds today. The actor configuration's `models` and `credentials` are being specified ([actor configuration spec](spec/actor-configuration.md)). The engine adapter will follow ([roadmap](../ROADMAP.md), milestone 2); a spike has already tried it on real models ([spike report](spikes/pydantic-ai.md)).

## Each actor brings its own models and keys

The model is the actor's choice, set in its own configuration (D11). Neither the script nor the play chooses it. A role can only hint, through `model.needs` and `suggested`.

An actor configuration lists its models in order. The first is used, and the next when one fails, which is also how an actor escalates from a local model to a cloud one. The configuration also holds this instance's credentials (D15):

- API keys for its models;
- tokens or key paths for its tools, such as GitHub or an SSH terminal.

Two actors on one machine have two configuration files, each with its own models and access.

## Secrets: only in actor configurations

- **Roles, scripts and plays never hold secrets.** They are shared and published, so `zanni` rejects any key in them that looks like a secret (`api_key`, `token`, `password`, `client_secret`, …).
- **An actor configuration may hold its own credentials.** It is an instance file, not project code, and never goes in a repository. `zanni` protects it:
  - it refuses a configuration that other users can read, and gives the `chmod` to run;
  - it refuses one that git tracks;
  - it never prints, logs or sends credentials to the director.
- **A credential may come from the environment instead**, as `${VAR}`. This is useful in CI.

## Any model, local or cloud

No role, script or play depends on a particular model or vendor:

- **Roles state what they need:** tool calling, a context size, a tier such as `judgement`. A role may suggest a default.
- **Local models aren't tied to one server.** They are reached through any OpenAI-compatible endpoint: Ollama, LM Studio, llama.cpp, vLLM and others. You don't need a local server if you use a cloud model, and you don't need a cloud key if you only use local models.
- **Models without native tool calling** can use an opt-in text-based tool format. It is opt-in per model, so models that call tools natively are never affected (D5).
- **Quality is checked, not assumed.** The director can't see which model an actor used, so verifiers decide whether work is done.

## Cost

- **Priced models:** a seat's cost comes from published prices, for the cloud models those prices cover.
- **Local models:** the actor's configuration can declare a price, which can be 0 for its own hardware.
- **Unknown cost is never counted as zero.** The director treats a seat with an unknown cost as unsafe for the play's budget (D7).
