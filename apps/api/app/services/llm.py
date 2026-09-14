"""
Model-provider abstraction. This is the ONLY module that knows how to actually talk
to Anthropic or Ollama -- everything upstream (agent.py, skills) calls
`complete(system, messages)` and gets back a provider-agnostic `LLMResult`.
Switching MODEL_PROVIDER in .env changes which branch runs; no other code changes.
"""
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class LLMProviderError(Exception):
    """Raised for any provider failure (missing key, unreachable, timeout, API
    error). Always caught by the caller and turned into a structured error
    response -- never allowed to crash the request."""

    def __init__(self, provider: str, detail: str):
        self.provider = provider
        self.detail = detail
        super().__init__(f"[{provider}] {detail}")


@dataclass
class LLMResult:
    text: str
    provider: str
    model_name: str


def complete(
    system: str, messages: list[dict], settings: Settings | None = None, max_tokens: int = 800
) -> LLMResult:
    """messages: [{"role": "user"|"assistant", "content": str}, ...]

    max_tokens: output budget. Callers set this per-skill -- a QA answer needs far
    fewer tokens than a ~1,250-word Ship 30 essay or a full HTML artifact, and on
    the local provider a smaller budget also means less time spent generating on
    constrained CPU hardware."""
    settings = settings or get_settings()

    if settings.model_provider == "anthropic":
        return _complete_anthropic(system, messages, settings, max_tokens)
    elif settings.model_provider == "ollama":
        return _complete_ollama(system, messages, settings, max_tokens)
    else:
        raise LLMProviderError(settings.model_provider, f"Unknown model provider '{settings.model_provider}'")


def _complete_anthropic(system: str, messages: list[dict], settings: Settings, max_tokens: int) -> LLMResult:
    if not settings.anthropic_api_key:
        raise LLMProviderError(
            "anthropic",
            "ANTHROPIC_API_KEY is not set. Add it to .env, or switch MODEL_PROVIDER to 'ollama'.",
        )
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        return LLMResult(text=text, provider="anthropic", model_name=settings.anthropic_model)
    except LLMProviderError:
        raise
    except Exception as e:  # noqa: BLE001 -- any SDK/network error becomes a structured provider error
        logger.error("anthropic_call_failed", error=str(e))
        raise LLMProviderError("anthropic", f"Anthropic API call failed: {e}") from e


def _complete_ollama(system: str, messages: list[dict], settings: Settings, max_tokens: int) -> LLMResult:
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": system}, *messages],
        "stream": False,
        # Ollama defaults num_ctx to 2048 regardless of what the model actually
        # supports, silently truncating/starving longer prompts (discovered live:
        # a 5-chunk RAG prompt returned HTTP 200 with an empty completion -- no
        # error, just nothing, because the truncated context left no room to
        # generate). Explicitly request the model's real context window instead.
        "options": {"num_ctx": settings.ollama_num_ctx, "num_predict": max_tokens},
    }
    try:
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
            timeout=settings.ollama_timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("message", {}).get("content", "")
        return LLMResult(text=text, provider="ollama", model_name=settings.ollama_model)
    except httpx.ConnectError as e:
        logger.error("ollama_unreachable", base_url=settings.ollama_base_url)
        raise LLMProviderError(
            "ollama",
            f"Ollama is not reachable at {settings.ollama_base_url}. Is 'ollama serve' running?",
        ) from e
    except httpx.TimeoutException as e:
        logger.error("ollama_timeout", base_url=settings.ollama_base_url)
        raise LLMProviderError("ollama", f"Ollama timed out after {settings.ollama_timeout_seconds}s.") from e
    except httpx.HTTPStatusError as e:
        logger.error("ollama_http_error", status=e.response.status_code, body=e.response.text[:500])
        raise LLMProviderError(
            "ollama",
            f"Ollama returned HTTP {e.response.status_code}. Is model '{settings.ollama_model}' pulled? "
            f"(`ollama pull {settings.ollama_model}`)",
        ) from e
