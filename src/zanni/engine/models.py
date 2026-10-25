"""Build a Pydantic AI model from a resolved actor-configuration model entry (D11, D20)."""

import os

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider

from zanni.actor.contract import ResolvedModel


def model_settings(rm: ResolvedModel, *, cache_instructions: bool = False) -> dict | None:
    """The settings for one model entry's requests: its `max_output` (D61), and, for the director, the provider's
    prompt caching of its instructions and tool definitions, which every turn sends again (D49, D61). Caching is
    Anthropic's explicit cache here; OpenAI caches long prompts on its own. Seats don't cache until measured."""
    settings: dict = {}
    if rm.entry.max_output:
        settings["max_tokens"] = rm.entry.max_output
    if cache_instructions and rm.entry.provider == "anthropic":
        settings["anthropic_cache_instructions"] = True
        settings["anthropic_cache_tool_definitions"] = True
    return settings or None


class ModelSetupError(Exception):
    """A model entry that can't be built: a missing package, a missing URL. Plain words for the user."""


def ollama_v1(url: str) -> str:
    """Pydantic AI's Ollama provider talks to Ollama's OpenAI-compatible API, under /v1 (spike finding)."""
    url = url.rstrip("/")
    return url if url.endswith("/v1") else url + "/v1"


def build_model(rm: ResolvedModel) -> Model:
    entry = rm.entry
    if entry.provider == "anthropic":
        model: Model = AnthropicModel(entry.model, provider=AnthropicProvider(api_key=rm.api_key, base_url=rm.base_url))
    elif entry.provider == "openai":
        model = OpenAIChatModel(entry.model, provider=OpenAIProvider(api_key=rm.api_key, base_url=rm.base_url))
    elif entry.provider == "ollama":
        url = rm.base_url or os.environ.get("OLLAMA_BASE_URL")
        if not url:
            raise ModelSetupError(f"{rm.label()}: no Ollama URL; set `base_url` in the model entry, or OLLAMA_BASE_URL")
        model = OllamaModel(entry.model, provider=OllamaProvider(base_url=ollama_v1(url), api_key=rm.api_key))
    elif entry.provider == "openai-compatible":
        model = OpenAIChatModel(entry.model, provider=OpenAIProvider(base_url=rm.base_url, api_key=rm.api_key or "not-set"))
    elif entry.provider == "google":
        try:
            from pydantic_ai.models.google import GoogleModel
            from pydantic_ai.providers.google import GoogleProvider
        except ImportError:
            raise ModelSetupError(f"{rm.label()}: Google models need the `google` extra; "
                                  "install it with: uv sync --extra google") from None
        model = GoogleModel(entry.model, provider=GoogleProvider(api_key=rm.api_key))
    else:  # the schema allows no other provider
        raise ModelSetupError(f"{rm.label()}: unknown provider")
    if entry.tool_format == "text":
        from zanni.engine.text_tools import TextToolsModel
        model = TextToolsModel(model)
    return model
