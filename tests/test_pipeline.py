"""
Integration-style tests for the pipeline (runs without real API keys
by relying on mock/stub providers).
"""

from __future__ import annotations

import pytest

from src.models import InputMode, PipelineInput, PipelineResult
from src.pipeline import run_pipeline
from src.providers.llm_provider import LLMProvider


# ---------------------------------------------------------------------------
# Fake LLM provider for deterministic tests
# ---------------------------------------------------------------------------


class FakeLLMProvider:
    """Returns canned normalization and translation JSON without hitting any API."""

    name = "fake"

    def complete(self, prompt: str, system: str = "") -> str:
        # Decide response type from system prompt keywords
        if "NORMALIZATION" in system or "normalize" in system.lower() or "cleaned_line" in system:
            lines = [
                line.split(". ", 1)[-1]
                for line in prompt.splitlines()
                if line.strip() and line[0].isdigit()
            ]
            import json
            return json.dumps([
                {
                    "original_line": line,
                    "cleaned_line": f"[cleaned] {line}",
                    "is_pidgin_heavy": True,
                    "ambiguous_phrases": [],
                }
                for line in lines
            ])

        if "translation_literal" in system or "Translate" in prompt:
            count = prompt.count("original:")
            import json
            return json.dumps([
                {
                    "translation_literal": f"literal translation {i+1}",
                    "translation_natural": f"natural translation {i+1}",
                    "confidence": 0.9,
                    "slang_explanation": "some slang explained",
                    "notes": "",
                }
                for i in range(max(count, 1))
            ])

        # Song summary
        import json
        return json.dumps({
            "main_theme": "Love and admiration",
            "emotional_tone": "Romantic",
            "recurring_slang": ["omo", "dey"],
            "plain_english_summary": "The artist expresses deep admiration for a romantic partner.",
            "language_mix": ["Nigerian Pidgin", "English"],
        })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_lyrics_song_mode_mock():
    """Pipeline should succeed end-to-end with mock lyrics + fake LLM."""
    pi = PipelineInput(
        mode=InputMode.LYRICS_SONG,
        song_title="Essence",
        artist="Wizkid",
        output_formats=[],
    )
    result = run_pipeline(pi, llm=FakeLLMProvider())
    assert result.error is None
    assert len(result.line_translations) > 0
    assert result.song_summary.main_theme != ""


def test_lyrics_text_mode():
    """Pipeline should handle raw text input."""
    raw = "Omo, you dey make my heart race\nE be like say na God send you"
    pi = PipelineInput(
        mode=InputMode.LYRICS_TEXT,
        song_title="Test Song",
        artist="Test Artist",
        raw_lyrics=raw,
        output_formats=[],
    )
    result = run_pipeline(pi, llm=FakeLLMProvider())
    assert result.error is None
    assert len(result.line_translations) == 2


def test_missing_lyrics_text_raises():
    """LYRICS_TEXT mode without raw_lyrics should return an error."""
    pi = PipelineInput(
        mode=InputMode.LYRICS_TEXT,
        output_formats=[],
    )
    result = run_pipeline(pi, llm=FakeLLMProvider())
    assert result.error is not None


def test_audio_file_not_found():
    """A non-existent audio file should return an error, not raise."""
    pi = PipelineInput(
        mode=InputMode.AUDIO_FILE,
        audio_file_path="/tmp/does_not_exist.mp3",
        output_formats=[],
    )
    result = run_pipeline(pi, llm=FakeLLMProvider())
    assert result.error is not None


def test_result_structure():
    """PipelineResult should carry expected fields."""
    pi = PipelineInput(
        mode=InputMode.LYRICS_SONG,
        song_title="Fall",
        artist="Davido",
        output_formats=[],
    )
    result = run_pipeline(pi, llm=FakeLLMProvider())
    assert isinstance(result, PipelineResult)
    for lt in result.line_translations:
        assert lt.line_number >= 1
        assert isinstance(lt.confidence, float)
        assert 0.0 <= lt.confidence <= 1.0
