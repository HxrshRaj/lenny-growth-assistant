"""
Model-provider toggle logic. Exercises the real branching/failure-handling code in
app/services/llm.py (no mocking of the branch itself) -- only the network-facing
edge (an unreachable host / missing key) is what we're deliberately triggering,
since a real, portable test can't depend on a live Anthropic key or a specific
Ollama model being pulled on whatever machine runs it.
"""
import pytest

from app.config import Settings
from app.services.llm import LLMProviderError, complete


def test_anthropic_without_api_key_raises_structured_error():
    settings = Settings(model_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(LLMProviderError) as exc_info:
        complete("system prompt", [{"role": "user", "content": "hi"}], settings)
    assert exc_info.value.provider == "anthropic"
    assert "ANTHROPIC_API_KEY" in exc_info.value.detail


def test_ollama_unreachable_raises_structured_error_not_crash():
    settings = Settings(model_provider="ollama", ollama_base_url="http://localhost:1", ollama_timeout_seconds=2)
    with pytest.raises(LLMProviderError) as exc_info:
        complete("system prompt", [{"role": "user", "content": "hi"}], settings)
    assert exc_info.value.provider == "ollama"
    assert "not reachable" in exc_info.value.detail.lower()


def test_unknown_provider_raises_structured_error():
    settings = Settings.model_construct(model_provider="carrier-pigeon")  # bypass Literal validation on purpose
    with pytest.raises(LLMProviderError):
        complete("system prompt", [{"role": "user", "content": "hi"}], settings)


def test_config_settings_default_to_ollama_for_local_demo():
    # The assignment mandates the demo run on Ollama; confirm that's still the
    # shipped default if no MODEL_PROVIDER env var is set.
    import os

    env_backup = os.environ.pop("MODEL_PROVIDER", None)
    try:
        settings = Settings(_env_file=None)
        assert settings.model_provider == "ollama"
    finally:
        if env_backup is not None:
            os.environ["MODEL_PROVIDER"] = env_backup
