import pytest

from zanni.actor.resolve import Unresolved, expand, resolve_models
from zanni.files.schemas import ActorConfiguration

FAKE = "sk-fake-0000"


def actor(**over):
    data = {"role": "roles/x", "play": "./p.yaml",
            "models": [{"provider": "anthropic", "model": "claude-haiku-5-5", "credential": "ANTHROPIC_API_KEY"},
                       {"provider": "ollama", "model": "qwen3.8:27b", "base_url": "${OLLAMA_BASE_URL}"}],
            "credentials": {"ANTHROPIC_API_KEY": FAKE, "GITHUB_TOKEN": "${GH_TOKEN}"}}
    data.update(over)
    return ActorConfiguration.model_validate(data)


def test_credentials_come_first_then_the_environment():
    models = resolve_models(actor(), env={"OLLAMA_BASE_URL": "http://gpu:11434", "ANTHROPIC_API_KEY": "env-key"})
    assert models[0].api_key == FAKE
    assert models[1].base_url == "http://gpu:11434"


def test_a_credential_that_is_a_reference_reads_the_environment():
    assert expand("${GITHUB_TOKEN}", {"GITHUB_TOKEN": "${GH_TOKEN}"}, {"GH_TOKEN": "ghp-fake"}) == "ghp-fake"


def test_defaults_apply_when_nothing_is_set():
    assert expand("${PORT:-8000}", {}, {}) == "8000"


def test_a_missing_value_is_reported_in_plain_words():
    with pytest.raises(Unresolved, match=r"\$\{OLLAMA_BASE_URL\} has no value: add OLLAMA_BASE_URL"):
        resolve_models(actor(), env={})


def test_without_a_credential_the_providers_usual_variable_is_used():
    a = actor(models=[{"provider": "anthropic", "model": "claude-haiku-5-5"}], credentials={})
    assert resolve_models(a, env={"ANTHROPIC_API_KEY": "env-key"})[0].api_key == "env-key"
    assert resolve_models(a, env={})[0].api_key is None


def test_a_model_whose_credential_is_missing_is_skipped_not_fatal():
    from zanni.actor.resolve import resolve_usable_models
    a = actor(credentials={"ANTHROPIC_API_KEY": "${NOT_SET}"})
    usable, skipped = resolve_usable_models(a, env={"OLLAMA_BASE_URL": "http://gpu:11434"})
    assert [m.entry.model for m in usable] == ["qwen3.8:27b"]
    assert skipped[0][0] == "anthropic claude-haiku-5-5" and "${NOT_SET} has no value" in skipped[0][1]
