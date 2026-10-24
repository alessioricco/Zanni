"""Fakes for engine tests: a stage in memory, and scripted models. No network, no keys."""

from __future__ import annotations  # a `list` method shadows `list` in the class body; Python < 3.14 evaluates eagerly

from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from zanni.actor.contract import ResolvedModel, StageError
from zanni.files.schemas import ModelEntry


class MemoryStage:
    def __init__(self, files: dict[str, str] | None = None, writable: tuple[str, ...] = ("tests/",)):
        self.files = dict(files or {})
        self.writable = writable
        self.log: list[tuple[str, str]] = []

    def read(self, path):
        if path not in self.files:
            raise StageError("not-found", f"{path} doesn't exist")
        return self.files[path]

    def write(self, path, content):
        if not path.startswith(self.writable):
            raise StageError("not-permitted", f"this seat may not write {path}")
        self.files[path] = content
        self.log.append((path, "written"))
        return str(len(self.log))

    def list(self, path=""):
        return sorted(p for p in self.files if p.startswith(path))

    def delete(self, path):
        self.files.pop(path)
        self.log.append((path, "deleted"))
        return str(len(self.log))

    def changes(self, since=None):
        return self.log[int(since or 0):], str(len(self.log))


def entry(model="m", **kw) -> ResolvedModel:
    return ResolvedModel(ModelEntry(provider="ollama", model=model, **kw), base_url="http://localhost:11434")


def scripted(*turns, name="scripted"):
    """A model that plays the given turns in order: a dict of tool calls, a string reply, or an exception to raise."""
    turns = list(turns)
    seen: list = []  # every message the model was sent, for tests to inspect

    def respond(messages, info: AgentInfo) -> ModelResponse:
        seen[:] = messages
        turn = turns.pop(0)
        if isinstance(turn, BaseException):
            raise turn
        if isinstance(turn, dict):
            return ModelResponse(parts=[ToolCallPart(name, args) for name, args in turn.items()])
        return ModelResponse(parts=[TextPart(turn)])

    model = FunctionModel(respond, model_name=name)
    model.seen = seen
    return model
