"""What the two Agent Cards carry in the casting extension's params (D21, D22).

The director serves its card at A2A's well-known path. The actor never listens, so it sends its card
inside its join message. A2A's own card fields (name, version, description, skills) are used as A2A
defines them; only what A2A has no field for goes in the extension's params.
"""

from typing import Annotated, Literal

from pydantic import Field

from zanni.protocol.encoding import Wire

EXTENSION_URI = "https://github.com/alessioricco/Zanni/blob/master/docs/spec/casting-extension.md#v4"
HASH = r"^sha256:[0-9a-f]{64}$"
Hash = Annotated[str, Field(pattern=HASH, description="A package's content hash, as in play.lock (D18).")]


class RoleNeeds(Wire):
    stage_read: list[str] = []
    stage_write: list[str] = []
    tools: list[str] = []


class ModelNeeds(Wire):
    """Hints only (D11): the director never checks a model against them."""

    tools: bool = False
    context: str | None = Field(default=None, pattern=r"^\d+[kKmM]?$")
    tier: str | None = None


class RoleOnCard(Wire):
    ref: str = Field(min_length=1, description="The package reference the actor was started with.")
    hash: Hash
    name: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")
    needs: RoleNeeds = RoleNeeds()
    never: list[str] = []
    model_needs: ModelNeeds = ModelNeeds()


class ReportedModel(Wire):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)


class ActorCardParams(Wire):
    """The casting extension's params on an actor's card."""

    kind: Literal["zanni.actor-card"] = "zanni.actor-card"
    actor: str | None = Field(default=None, min_length=1, description="The configuration's `name`.")
    role: RoleOnCard
    models: list[ReportedModel] = Field(default=[], description="Self-reported, logged, never trusted (D11).")


class DirectorCardParams(Wire):
    """The casting extension's params on the director's card."""

    kind: Literal["zanni.director-card"] = "zanni.director-card"
    play: str = Field(min_length=1, description="The play's `name`.")
    script: str = Field(min_length=1, description="The play's `script` reference.")
