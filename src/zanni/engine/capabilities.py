"""Ask a local Ollama server what a model can do, so a missing capability is caught before a run (D5)."""

import httpx

from zanni.actor.contract import ResolvedModel
from zanni.engine.models import ModelSetupError


def ollama_capabilities(base_url: str, model: str, timeout: float = 10) -> list[str] | None:
    """The model's capabilities from /api/show, or None if the server can't be asked (the run's fallback handles that)."""
    root = base_url.rstrip("/").removesuffix("/v1")
    try:
        response = httpx.post(f"{root}/api/show", json={"model": model}, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    return response.json().get("capabilities")


def check_tool_support(rm: ResolvedModel, needs_tools: bool, base_url: str | None) -> None:
    if not (needs_tools and rm.entry.provider == "ollama" and rm.entry.tool_format == "native" and base_url):
        return
    capabilities = ollama_capabilities(base_url, rm.entry.model)
    if capabilities is not None and "tools" not in capabilities:
        raise ModelSetupError(f"{rm.label()} can't call tools natively (its capabilities: {', '.join(capabilities)}), "
                              "and this role needs tools; add `tool_format: text` to its model entry")
