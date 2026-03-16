"""
Configuration and settings for afrobeats-translator.
All secrets are read from environment variables; never hard-coded.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    provider: Literal["openai", "anthropic", "deepseek"] = "anthropic"
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    max_retries: int = 3
    timeout: float = 60.0

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-opus-4-6",
            "deepseek": "deepseek-chat",
        }
        return defaults[self.provider]


class TranscriptionConfig(BaseModel):
    provider: Literal["google", "openai_whisper", "stub"] = "openai_whisper"
    language_hints: list[str] = Field(
        default_factory=lambda: ["en-NG", "en", "yo", "ig", "pcm"]
    )


class AudioConfig(BaseModel):
    isolation_provider: Literal["elevenlabs", "demucs", "stub"] = "stub"
    sample_rate: int = 44100
    output_format: str = "wav"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")

    # Sub-configs (set via env as JSON or use defaults)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)

    # Output
    output_dir: str = "output"
    log_level: str = "INFO"

    def llm_api_key(self) -> str:
        """Return the correct API key for the configured LLM provider."""
        key_map = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "deepseek": self.deepseek_api_key,
        }
        return key_map.get(self.llm.provider, "")

    def has_llm_key(self) -> bool:
        return bool(self.llm_api_key())

    def has_google_key(self) -> bool:
        return bool(self.google_api_key)

    def has_elevenlabs_key(self) -> bool:
        return bool(self.elevenlabs_api_key)


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
