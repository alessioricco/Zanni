"""The engine adapter: the only part of Zanni that imports Pydantic AI, mcp or a2a-sdk (golden rule 4, D1).

Everything else talks to it through zanni.actor.contract: run_cue(CueTask) -> CueResult.
"""

import os

# Pydantic AI prints a promotional banner on every agent run unless this is set (D1).
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
