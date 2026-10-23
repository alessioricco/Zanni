"""Classify a model failure into the actor configuration's fallback reasons (D20)."""

from pydantic_ai.exceptions import (
    ContentFilterError, ModelAPIError, ModelContextWindowExceededError, ModelQuotaExceededError,
    ModelRateLimitError, ModelRequestTimeout, ModelTimeoutError,
)

# Order matters: a ModelTimeoutError is also a ModelConnectionError, so the specific types come first.
_REASONS: list[tuple[tuple[type[BaseException], ...], str]] = [
    ((ModelRateLimitError, ModelQuotaExceededError), "rate-limit"),
    ((ModelContextWindowExceededError,), "context"),
    ((ModelTimeoutError, ModelRequestTimeout, TimeoutError), "timeout"),
    ((ContentFilterError,), "refusal"),
    ((ModelAPIError, ConnectionError, OSError), "error"),
]


def classify(exc: BaseException) -> str | None:
    """The fallback reason for this failure, or None if it isn't a model failure (a bug, a cancelled run)."""
    for types, reason in _REASONS:
        if isinstance(exc, types):
            return reason
    return None
