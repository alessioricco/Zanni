import pytest

from tests.engine.fakes import entry
from zanni.engine import capabilities
from zanni.engine.models import ModelSetupError


def test_a_model_without_tools_is_refused_before_the_run(monkeypatch):
    monkeypatch.setattr(capabilities, "ollama_capabilities", lambda url, model: ["completion", "vision"])
    with pytest.raises(ModelSetupError, match="can't call tools natively .* add `tool_format: text`"):
        capabilities.check_tool_support(entry("gemma3:4b"), True, "http://gpu:11434")


def test_the_text_format_or_no_tool_needs_skip_the_check(monkeypatch):
    monkeypatch.setattr(capabilities, "ollama_capabilities", lambda url, model: ["completion"])
    capabilities.check_tool_support(entry("gemma3:4b", tool_format="text"), True, "http://gpu:11434")
    capabilities.check_tool_support(entry("gemma3:4b"), False, "http://gpu:11434")


def test_an_unreachable_server_is_left_to_the_fallback(monkeypatch):
    monkeypatch.setattr(capabilities, "ollama_capabilities", lambda url, model: None)
    capabilities.check_tool_support(entry("qwen3.8:27b"), True, "http://gpu:11434")
