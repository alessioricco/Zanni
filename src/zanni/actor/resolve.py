"""Resolve ${NAME} references from an actor configuration's credentials, then the environment (D20)."""

import os
import re
from collections.abc import Mapping

from zanni.actor.contract import ResolvedModel
from zanni.files.schemas import ActorConfiguration

REF = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>[^}]*))?\}")
# The environment variable each provider reads when an entry names no credential.
PROVIDER_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY",
                 "ollama": "OLLAMA_API_KEY", "openai-compatible": None}


class Unresolved(Exception):
    """A ${NAME} with no value in the credentials or the environment, and no default."""


def expand(value: str, credentials: Mapping[str, str], env: Mapping[str, str] | None = None) -> str:
    """Replace every ${NAME} (or ${NAME:-default}) in `value`. Credentials may themselves be ${VAR} references."""
    env = os.environ if env is None else env

    def lookup(m: re.Match) -> str:
        name, default = m["name"], m["default"]
        if name in credentials:
            return expand(credentials[name], {}, env)  # a credential's own ${VAR} reads the environment
        if name in env:
            return env[name]
        if default is not None:
            return default
        raise Unresolved(f"${{{name}}} has no value: add {name} to the actor configuration's `credentials`, "
                         "or set it in the environment")

    return REF.sub(lookup, value)


def resolve_models(actor: ActorConfiguration, env: Mapping[str, str] | None = None) -> list[ResolvedModel]:
    env = os.environ if env is None else env
    resolved = []
    for entry in actor.models:
        if entry.credential:
            api_key = expand(f"${{{entry.credential}}}", actor.credentials, env)
        else:
            var = PROVIDER_KEYS[entry.provider]
            api_key = expand(f"${{{var}}}", actor.credentials, env) if var and (var in actor.credentials or var in env) else None
        base_url = expand(entry.base_url, actor.credentials, env) if entry.base_url else None
        resolved.append(ResolvedModel(entry=entry, api_key=api_key, base_url=base_url))
    return resolved
