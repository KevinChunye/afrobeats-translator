"""Unit tests for the translation service."""

from __future__ import annotations

import json
import pytest

from src.models import LineTranslation
from src.services.normalize import NormalizedLine
from src.services.translate import translate_lines


# ---------------------------------------------------------------------------
# Fake LLM
# ---------------------------------------------------------------------------


class FakeTranslateLLM:
    name = "fake"

    def complete(self, prompt: str, system: str = "") -> str:
        count = prompt.count("original:")
        return json.dumps([
            {
                "translation_literal": f"literal {i + 1}",
                "translation_natural": f"natural {i + 1}",
                "confidence": 0.88,
                "slang_explanation": "dey = is/are in Pidgin",
                "notes": "",
            }
            for i in range(max(count, 1))
        ])


class ErrorLLM:
    name = "error"

    def complete(self, prompt: str, system: str = "") -> str:
        raise TimeoutError("API timeout")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _make_normalized(lines: list[str]) -> list[NormalizedLine]:
    return [
        NormalizedLine(
            original_line=line,
            cleaned_line=f"cleaned: {line}",
            is_pidgin_heavy="dey" in line,
            ambiguous_phrases=[],
        )
        for line in lines
    ]


def test_translate_returns_correct_count():
    nl = _make_normalized(["Omo, you dey make me smile", "I love you to the moon"])
    results = translate_lines(nl, llm=FakeTranslateLLM())
    assert len(results) == 2


def test_translate_line_numbers_are_sequential():
    nl = _make_normalized(["a", "b", "c"])
    results = translate_lines(nl, llm=FakeTranslateLLM())
    assert [r.line_number for r in results] == [1, 2, 3]


def test_translate_confidence_in_range():
    nl = _make_normalized(["Omo, dey vibe"])
    results = translate_lines(nl, llm=FakeTranslateLLM())
    for r in results:
        assert 0.0 <= r.confidence <= 1.0


def test_translate_fallback_on_error():
    """Should fall back to zero-confidence placeholders on LLM failure."""
    nl = _make_normalized(["e go be fine", "we outside"])
    results = translate_lines(nl, llm=ErrorLLM())
    assert len(results) == 2
    for r in results:
        assert r.confidence == 0.0
        assert "unavailable" in r.notes.lower()


def test_translate_preserves_original_line():
    nl = _make_normalized(["Your waist dey sweet my eye"])
    results = translate_lines(nl, llm=FakeTranslateLLM())
    assert results[0].original_line == "Your waist dey sweet my eye"


def test_translate_large_batch_chunking():
    """Ensure chunking works correctly for batches > chunk_size."""
    # chunk_size default is 15; let's use 20 lines
    nl = _make_normalized([f"line {i}" for i in range(20)])
    results = translate_lines(nl, llm=FakeTranslateLLM(), chunk_size=7)
    assert len(results) == 20
    assert [r.line_number for r in results] == list(range(1, 21))
