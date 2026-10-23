# Models and keys

> **Status:** nothing in Zanni calls a model yet. The rule about keys holds today. The rest of this page is the design the engine adapter will follow ([roadmap](../ROADMAP.md), milestone 2), which a spike has already tried on real models ([spike report](spikes/pydantic-ai.md)).

## Keys never go in files

No Zanni file takes an API key, and no `zanni` option does either. Put keys in the environment:

```bash
export ANTHROPIC_API_KEY=...
```

or in a `.env` file at the root of your working folder, which must be git-ignored. This repository's `.gitignore` already ignores `.env`:

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
OLLAMA_BASE_URL=http://my-gpu-box:11434
```

If a Zanni file has a key that looks like a secret, `zanni` rejects the file and tells you to move the value.

## Any model, local or cloud

No role, play or actor file depends on a particular model or vendor:

- **Roles state what they need:** tool calling, a context size, a tier such as `judgement`. A role may suggest a default.
- **The actor's host picks the model**, matching the role's needs against its own list of models. The same role runs on a local model on one machine and on a cloud model on another.
- **Local models aren't tied to one server.** They are reached through any OpenAI-compatible endpoint: Ollama, LM Studio, llama.cpp, vLLM and others. You don't need a local server at all if you use a cloud model, and you don't need a cloud key if you only use local models.
- **Models without native tool calling** can use an opt-in text-based tool format. It is opt-in per model, so models that call tools natively are never affected (D5).
- **Escalation:** a seat can start on a local model and move to a cloud model if it fails, with the director counting the cost.

## Cost

- **Priced models:** a seat's cost comes from published prices, for the cloud models those prices cover.
- **Local models:** the host declares a price, which can be 0 for its own hardware.
- **Unknown cost is never counted as zero.** The director treats a seat with an unknown cost as unsafe for the play's budget (D7).

**Draft:** the host files that hold a model list and prices (`models_list.yaml`, which is shareable, and `models.yaml`, which is personal) aren't specified yet.
