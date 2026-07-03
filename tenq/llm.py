"""Bring-your-own-LLM layer: Anthropic (default), OpenAI, or local Ollama.

Provider resolution order: explicit argument > TENQ_PROVIDER env var >
ANTHROPIC_API_KEY > OPENAI_API_KEY > local Ollama.
"""

from __future__ import annotations

import os

import requests

DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1",
}

OLLAMA_URL = os.environ.get("TENQ_OLLAMA_URL", "http://localhost:11434")


class LLMError(RuntimeError):
    pass


def resolve_provider(provider: str | None = None) -> str:
    provider = provider or os.environ.get("TENQ_PROVIDER")
    if provider:
        if provider not in DEFAULT_MODELS:
            raise LLMError(f"Unknown provider {provider!r}; expected one of {sorted(DEFAULT_MODELS)}")
        return provider
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if _ollama_alive():
        return "ollama"
    raise LLMError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY, "
        "run a local Ollama server, or use --no-llm for the data-only dossier."
    )


def complete(prompt: str, provider: str | None = None, model: str | None = None,
             max_tokens: int = 8000) -> str:
    provider = resolve_provider(provider)
    model = model or os.environ.get("TENQ_MODEL") or DEFAULT_MODELS[provider]
    if provider == "anthropic":
        return _anthropic(prompt, model, max_tokens)
    if provider == "openai":
        return _openai(prompt, model, max_tokens)
    return _ollama(prompt, model)


def _anthropic(prompt: str, model: str, max_tokens: int) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise LLMError("The anthropic package is required: pip install anthropic") from exc

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LLMError("ANTHROPIC_API_KEY is not set (required for --provider anthropic).")
    client = anthropic.Anthropic()
    kwargs: dict = {}
    # Claude 4.6+ models support adaptive thinking; older ones reject it.
    if not model.startswith(("claude-3", "claude-opus-4-0", "claude-opus-4-1", "claude-sonnet-4-0")):
        kwargs["thinking"] = {"type": "adaptive"}
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
    except anthropic.APIError as exc:
        raise LLMError(f"Anthropic API error: {exc}") from exc
    if response.stop_reason == "refusal":
        raise LLMError("The model declined this request (stop_reason=refusal).")
    text = "".join(block.text for block in response.content if block.type == "text")
    if not text:
        raise LLMError("Anthropic API returned no text content.")
    return text


def _openai(prompt: str, model: str, max_tokens: int) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise LLMError("OPENAI_API_KEY is not set (required for --provider openai).")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "max_completion_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=300,
    )
    if resp.status_code != 200:
        raise LLMError(f"OpenAI API error {resp.status_code}: {resp.text[:300]}")
    text = resp.json()["choices"][0]["message"]["content"]
    if not text:
        raise LLMError("OpenAI API returned no text content.")
    return text


def _ollama(prompt: str, model: str) -> str:
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=600,
    )
    if resp.status_code != 200:
        raise LLMError(f"Ollama error {resp.status_code}: {resp.text[:300]}")
    return resp.json().get("response", "")


def _ollama_alive() -> bool:
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).status_code == 200
    except requests.RequestException:
        return False
