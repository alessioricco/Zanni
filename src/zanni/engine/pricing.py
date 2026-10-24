"""Whether a model has a price: published (genai-prices, through Pydantic AI) or declared in its entry (D7, D39)."""

from genai_prices.data_snapshot import get_snapshot

from zanni.actor.contract import ResolvedModel

# Zanni's providers, as genai-prices names them; local servers have no published prices.
_PROVIDERS = {"anthropic": "anthropic", "openai": "openai", "google": "google"}


def has_price(rm: ResolvedModel) -> bool:
    if rm.entry.price is not None:
        return True
    provider = _PROVIDERS.get(rm.entry.provider)
    if provider is None:
        return False
    try:
        get_snapshot().find_provider_model(rm.entry.model, provider=None, provider_id=provider, provider_api_url=None)
    except LookupError:
        return False
    return True


def all_priced(models: list[ResolvedModel]) -> bool:
    return bool(models) and all(has_price(rm) for rm in models)
