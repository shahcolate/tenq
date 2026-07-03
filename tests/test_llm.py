import pytest

from tenq import llm


def test_resolve_provider_rejects_unknown():
    with pytest.raises(llm.LLMError):
        llm.resolve_provider("bard")


def test_openai_without_key_is_a_clean_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(llm.LLMError, match="OPENAI_API_KEY"):
        llm.complete("hi", provider="openai")


def test_no_provider_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TENQ_PROVIDER", raising=False)
    monkeypatch.setattr(llm, "_ollama_alive", lambda: False)
    with pytest.raises(llm.LLMError, match="No LLM provider"):
        llm.resolve_provider()
