"""The tools Zanni gives every actor: `load_skill` (D4) and the stage operations (docs/spec/stage.md)."""

import inspect

from pydantic_ai import FunctionToolset, ModelRetry

from zanni.actor.contract import Stage, StageError


def skill_toolset(skills: dict[str, str]) -> FunctionToolset:
    def load_skill(name: str) -> str:
        """Return the full instructions of one of your skills."""
        if name not in skills:
            raise ModelRetry(f"No skill named {name!r}; your skills are: {', '.join(sorted(skills)) or 'none'}.")
        return skills[name]

    return FunctionToolset([load_skill])


def stage_toolset(stage: Stage) -> FunctionToolset:
    """The five stage operations, with the same names and errors over MCP (D16, D31).

    `stage` is a seat's view on the director's side, or a RemoteStage over MCP: the tools are the same.
    """

    def refuse(e: StageError) -> Exception:
        if e.code == "unavailable":  # the model can't fix a stage that went away: the cue ends (D47)
            return e
        return ModelRetry(f"{e.code}: {e}")

    async def done(value):
        return await value if inspect.isawaitable(value) else value

    async def stage_read(path: str) -> str:
        """Read a file from the stage. Paths are relative to the stage root, e.g. backlog/round-1.md."""
        try:
            return await done(stage.read(path))
        except StageError as e:
            raise refuse(e) from None

    async def stage_write(path: str, content: str) -> str:
        """Write a whole file to the stage, replacing it if it exists. Returns the new change marker."""
        try:
            return await done(stage.write(path, content))
        except StageError as e:
            raise refuse(e) from None

    async def stage_list(path: str = "") -> list[str]:
        """List the files and folders under a stage folder that you may read; empty for the root."""
        try:
            return await done(stage.list(path))
        except StageError as e:
            raise refuse(e) from None

    async def stage_delete(path: str) -> str:
        """Delete a file from the stage. Returns the new change marker."""
        try:
            return await done(stage.delete(path))
        except StageError as e:
            raise refuse(e) from None

    async def stage_changes(since: str | None = None) -> dict:
        """What changed on the stage since a change marker (or since the start), and the current marker."""
        try:
            changes, marker = await done(stage.changes(since))
        except StageError as e:
            raise refuse(e) from None
        return {"changes": [{"path": p, "change": c} for p, c in changes], "marker": marker}

    # Sequential: several calls in one reply must reach the stage in the order the model wrote them.
    return FunctionToolset([stage_read, stage_write, stage_list, stage_delete, stage_changes], sequential=True)
