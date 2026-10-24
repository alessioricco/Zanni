"""The stage (docs/spec/stage.md): backends that store it, and the layer above them that enforces permissions (D43).

No engine imports here: the `mcp` backend's client lives in src/zanni/engine/.
"""

from pathlib import Path

from zanni.stage.errors import StageError
from zanni.stage.folder import FolderBackend
from zanni.stage.layer import Change, SeatStage, Stage
from zanni.stage.paths import check_path

__all__ = ["Change", "FolderBackend", "SeatStage", "Stage", "StageError", "check_path", "folder_stage"]


def folder_stage(root: Path) -> Stage:
    """A stage on a folder of this machine."""
    return Stage(FolderBackend(root))
