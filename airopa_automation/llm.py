"""
LLM wrapper — abstracts Groq and Mistral API calls.

Returns structured results for telemetry. Never raises into
business logic; callers check result["status"] instead.
"""

import logging
import time
from typing import Optional

from airopa_automation.config import config

logger = logging.getLogger(__name__)


def llm_complete(
    prompt: str,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> dict:
    """Call the configured LLM provider and return a structured result.

    Args:
        prompt: The prompt text to send.
        model: Override model name (defaults to config).
        temperature: Override temperature (defaults to config).

    Returns:
        Dict with keys:
            text: Response text (empty string on failure)
            latency_ms: Round-trip time in milliseconds
            tokens_in: Input token count (0 if unavailable)
            tokens_out: Output token count (0 if unavailable)
            status: "ok", "no_api_key", "api_error", "timeout", or "import_error"
            error: Error message (empty string on success)
            provider: "groq" or "mistral"
            model: Model name used
    """
    provider = config.ai.provider
    used_model = model or config.ai.model
    used_temp = temperature if temperature is not None else config.ai.temperature

    base = {
        "text": "",
        "latency_ms": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "status": "ok",
        "error": "",
        "provider": provider,
        "model": used_model,
    }

    api_key = config.ai.api_key
    if not api_key:
        base["status"] = "no_api_key"
        base["error"] = f"No API key configured for provider '{provider}'"
        logger.warning(base["error"])
        return base

    if provider == "mistral":
        return _call_mistral(prompt, used_model, used_temp, api_key, base)
    return _call_groq(prompt, used_model, used_temp, api_key, base)


def _call_groq(
    prompt: str, model: str, temperature: float, api_key: str, base: dict
) -> dict:
    """Call Groq API."""
    try:
        from groq import Groq
    except ImportError:
        base["status"] = "import_error"
        base["error"] = "groq package not installed"
        logger.error(base["error"])
        return base

    start = time.monotonic()
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=config.ai.max_tokens,
        )
        elapsed = (time.monotonic() - start) * 1000

        base["text"] = response.choices[0].message.content or ""
        base["latency_ms"] = round(elapsed)
        if response.usage:
            base["tokens_in"] = response.usage.prompt_tokens
            base["tokens_out"] = response.usage.completion_tokens
        return base

    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        base["latency_ms"] = round(elapsed)
        base["status"] = "api_error"
        base["error"] = str(e)
        logger.error("Groq API error: %s", e)
        return base


def _call_mistral(
    prompt: str, model: str, temperature: float, api_key: str, base: dict
) -> dict:
    """Call Mistral API."""
    try:
        from mistralai import Mistral
    except ImportError:
        base["status"] = "import_error"
        base["error"] = "mistralai package not installed"
        logger.error(base["error"])
        return base

    start = time.monotonic()
    try:
        client = Mistral(api_key=api_key)
        response = client.chat.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=config.ai.max_tokens,
        )
        elapsed = (time.monotonic() - start) * 1000

        base["text"] = response.choices[0].message.content or ""
        base["latency_ms"] = round(elapsed)
        if response.usage:
            base["tokens_in"] = response.usage.prompt_tokens
            base["tokens_out"] = response.usage.completion_tokens
        return base

    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        base["latency_ms"] = round(elapsed)
        base["status"] = "api_error"
        base["error"] = str(e)
        logger.error("Mistral API error: %s", e)
        return base
