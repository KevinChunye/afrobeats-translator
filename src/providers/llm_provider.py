"""
LLM provider abstractions.

Supported providers:
  - AnthropicProvider  (claude-opus-4-6 etc.)
  - OpenAIProvider     (gpt-4o etc.)
  - DeepSeekProvider   (deepseek-chat — OpenAI-compatible endpoint)

Each provider exposes a single `complete(prompt, system)` method that returns
a plain string response.  Retries with exponential back-off are handled here.
"""

from __future__ import annotations

import abc
import time
from typing import Protocol

from ..config import LLMConfig, get_settings
from ..logger import get_logger

logger = get_logger(__name__)


class LLMProvider(Protocol):
    """Minimal interface every LLM backend must satisfy."""

    def complete(self, prompt: str, system: str = "") -> str:
        ...

    @property
    def name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._cfg = config or get_settings().llm
        self._client = self._build_client()

    def _build_client(self):  # type: ignore[return]
        try:
            import anthropic

            key = get_settings().anthropic_api_key
            if not key:
                logger.warning("ANTHROPIC_API_KEY not set – AnthropicProvider unavailable")
                return None
            return anthropic.Anthropic(api_key=key)
        except ImportError:
            logger.warning("anthropic package not installed")
            return None

    def complete(self, prompt: str, system: str = "") -> str:
        if self._client is None:
            raise RuntimeError("Anthropic client not initialised (missing key or package)")

        model = self._cfg.resolved_model()
        messages = [{"role": "user", "content": prompt}]

        for attempt in range(self._cfg.max_retries):
            try:
                kwargs: dict = dict(
                    model=model,
                    max_tokens=self._cfg.max_tokens,
                    temperature=self._cfg.temperature,
                    messages=messages,
                )
                if system:
                    kwargs["system"] = system

                response = self._client.messages.create(**kwargs)
                return response.content[0].text  # type: ignore[index]
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning(
                    f"Anthropic attempt {attempt + 1}/{self._cfg.max_retries} failed: {exc}. "
                    f"Retrying in {wait}s…"
                )
                if attempt < self._cfg.max_retries - 1:
                    time.sleep(wait)
        raise RuntimeError("Anthropic provider exhausted all retries")


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIProvider:
    name = "openai"

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._cfg = config or get_settings().llm
        self._client = self._build_client()

    def _build_client(self):  # type: ignore[return]
        try:
            from openai import OpenAI

            key = get_settings().openai_api_key
            if not key:
                logger.warning("OPENAI_API_KEY not set – OpenAIProvider unavailable")
                return None
            return OpenAI(api_key=key)
        except ImportError:
            logger.warning("openai package not installed")
            return None

    def complete(self, prompt: str, system: str = "") -> str:
        if self._client is None:
            raise RuntimeError("OpenAI client not initialised")

        model = self._cfg.resolved_model()
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(self._cfg.max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=self._cfg.max_tokens,
                    temperature=self._cfg.temperature,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning(f"OpenAI attempt {attempt + 1} failed: {exc}. Retrying in {wait}s…")
                if attempt < self._cfg.max_retries - 1:
                    time.sleep(wait)
        raise RuntimeError("OpenAI provider exhausted all retries")


# ---------------------------------------------------------------------------
# DeepSeek (OpenAI-compatible)
# ---------------------------------------------------------------------------


class DeepSeekProvider:
    """
    DeepSeek uses an OpenAI-compatible REST API.
    Base URL: https://api.deepseek.com
    TODO: Verify endpoint path if DeepSeek updates their API.
    """

    name = "deepseek"

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._cfg = config or get_settings().llm
        self._client = self._build_client()

    def _build_client(self):  # type: ignore[return]
        try:
            from openai import OpenAI

            key = get_settings().deepseek_api_key
            if not key:
                logger.warning("DEEPSEEK_API_KEY not set – DeepSeekProvider unavailable")
                return None
            return OpenAI(api_key=key, base_url="https://api.deepseek.com")
        except ImportError:
            logger.warning("openai package not installed (needed for DeepSeek adapter)")
            return None

    def complete(self, prompt: str, system: str = "") -> str:
        if self._client is None:
            raise RuntimeError("DeepSeek client not initialised")

        model = self._cfg.resolved_model()
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(self._cfg.max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=self._cfg.max_tokens,
                    temperature=self._cfg.temperature,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                wait = 2 ** attempt
                logger.warning(f"DeepSeek attempt {attempt + 1} failed: {exc}. Retrying in {wait}s…")
                if attempt < self._cfg.max_retries - 1:
                    time.sleep(wait)
        raise RuntimeError("DeepSeek provider exhausted all retries")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class FallbackProvider:
    """
    Wraps multiple providers in priority order.
    On each `complete()` call, tries providers in sequence until one succeeds.
    This handles keys that are set but fail at runtime (rate limits, bad key, etc.).
    """

    def __init__(self, providers: list) -> None:
        self._providers = providers

    @property
    def name(self) -> str:
        return " -> ".join(p.name for p in self._providers)

    def complete(self, prompt: str, system: str = "") -> str:
        last_exc: Exception = RuntimeError("No providers available")
        for provider in self._providers:
            try:
                result = provider.complete(prompt, system)
                return result
            except Exception as exc:
                logger.warning(f"Provider '{provider.name}' failed: {exc}. Trying next…")
                last_exc = exc
        raise last_exc


def build_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """
    Return the best available LLM provider.

    Priority: Anthropic → OpenAI → DeepSeek.
    Only providers with a key set are included.
    If a specific provider_name is requested, use that first then fall back.
    """
    settings = get_settings()
    name = provider_name or settings.llm.provider

    registry: dict[str, type] = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "deepseek": DeepSeekProvider,
    }

    if name not in registry:
        raise ValueError(f"Unknown LLM provider: {name!r}. Choose from {list(registry)}")

    # Build list of providers that have keys, starting with the preferred one
    key_map = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "deepseek": settings.deepseek_api_key,
    }
    # Fallback order: preferred first, then others
    fallback_order = [name] + [k for k in ["anthropic", "openai", "deepseek"] if k != name]
    active = []
    for pname in fallback_order:
        if key_map.get(pname):
            cfg = LLMConfig(provider=pname)  # type: ignore[arg-type]
            active.append(registry[pname](cfg))

    if not active:
        raise RuntimeError(
            "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file."
        )

    if len(active) == 1:
        logger.info(f"Using {active[0].name} provider")
        return active[0]  # type: ignore[return-value]

    logger.info(f"Using provider chain: {' -> '.join(p.name for p in active)}")
    return FallbackProvider(active)  # type: ignore[return-value]
