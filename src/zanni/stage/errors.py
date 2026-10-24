"""The stage's errors (docs/spec/stage.md, "Operations"): one exception, with the spec's code."""

CODES = ("invalid-path", "not-permitted", "not-found", "not-text", "unknown-marker", "unavailable")


class StageError(Exception):
    """A refused stage operation; `code` is one of the stage spec's errors."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
