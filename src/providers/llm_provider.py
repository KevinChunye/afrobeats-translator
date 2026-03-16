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


def build_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Return the best available LLM provider."""
    settings = get_settings()
    name = provider_name or settings.llm.provider

    registry: dict[str, type] = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "deepseek": DeepSeekProvider,
    }

    if name not in registry:
        raise ValueError(f"Unknown LLM provider: {name!r}. Choose from {list(registry)}")

    provider = registry[name]()

    # Graceful fallback chain: if primary has no key, try others.
    # When falling back we build a fresh LLMConfig scoped to the new provider
    # so resolved_model() returns the correct model name (not the Anthropic one).
    if name == "anthropic" and not settings.anthropic_api_key:
        if settings.openai_api_key:
            logger.warning("Falling back to OpenAI provider")
            return OpenAIProvider(LLMConfig(provider="openai"))
        if settings.deepseek_api_key:
            logger.warning("Falling back to DeepSeek provider")
            return DeepSeekProvider(LLMConfig(provider="deepseek"))

    return provider  # type: ignore[return-value]
