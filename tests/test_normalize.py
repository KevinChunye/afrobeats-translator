"""Unit tests for normalization utilities and text helpers."""

from __future__ import annotations

import json
import pytest

from src.models import RawLyrics
from src.services.normalize import NormalizedLine, normalize_lyrics
from src.utils.text import safe_json_parse, clean_lyric_text, chunk_lines


# ---------------------------------------------------------------------------
# safe_json_parse
# ---------------------------------------------------------------------------


def test_parse_clean_json():
    data = [{"key": "value"}]
    assert safe_json_parse(json.dumps(data)) == data


def test_parse_with_markdown_fences():
    raw = "```json\n[{\"a\": 1}]\n```"
    assert safe_json_parse(raw) == [{"a": 1}]


def test_parse_with_preamble():
    raw = "Here is the result:\n[{\"x\": 2}]"
    assert safe_json_parse(raw) == [{"x": 2}]


def test_parse_object():
    raw = '{"main_theme": "love"}'
    assert safe_json_parse(raw) == {"main_theme": "love"}


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        safe_json_parse("this is not json at all and has no brackets")


# ---------------------------------------------------------------------------
# clean_lyric_text
# ---------------------------------------------------------------------------


def test_clean_removes_section_headers():
    text = "[Chorus]\nOmo, you dey sweet my eye\n[Verse 1]\nE be like say na God"
    cleaned = clean_lyric_text(text)
    assert "[Chorus]" not in cleaned
    assert "[Verse 1]" not in cleaned
    assert "Omo, you dey sweet my eye" in cleaned


def test_clean_strips_blank_lines():
    text = "line one\n\n  \nline two\n"
    cleaned = clean_lyric_text(text)
    assert cleaned == "line one\nline two"


# ---------------------------------------------------------------------------
# chunk_lines
# ---------------------------------------------------------------------------


def test_chunk_exact():
    lines = ["a", "b", "c", "d"]
    chunks = list(chunk_lines(lines, 2))
    assert chunks == [["a", "b"], ["c", "d"]]


def test_chunk_remainder():
    lines = ["a", "b", "c"]
    chunks = list(chunk_lines(lines, 2))
    assert chunks == [["a", "b"], ["c"]]


def test_chunk_larger_than_list():
    lines = ["a"]
    chunks = list(chunk_lines(lines, 10))
    assert chunks == [["a"]]


# ---------------------------------------------------------------------------
# normalize_lyrics (with fake LLM)
# ---------------------------------------------------------------------------


class FakeLLM:
    name = "fake"

    def complete(self, prompt: str, system: str = "") -> str:
        lines_in_prompt = [
            part.split(". ", 1)[-1]
            for part in prompt.splitlines()
            if part.strip() and part[0].isdigit()
        ]
        return json.dumps([
            {
                "original_line": line,
                "cleaned_line": f"cleaned: {line}",
                "is_pidgin_heavy": "dey" in line.lower() or "omo" in line.lower(),
                "ambiguous_phrases": [],
            }
            for line in lines_in_prompt
        ])


def test_normalize_preserves_line_count():
    lyrics = RawLyrics(
        raw_text="Omo, you dey make me smile\nE be like say na God send you\nI no go forget this day",
        source="test",
    )
    normalized = normalize_lyrics(lyrics, llm=FakeLLM())
    assert len(normalized) == 3


def test_normalize_detects_pidgin():
    lyrics = RawLyrics(
        raw_text="Omo, you dey here\nI love you",
        source="test",
    )
    normalized = normalize_lyrics(lyrics, llm=FakeLLM())
    pidgin_flags = [n.is_pidgin_heavy for n in normalized]
    # First line has "omo" and "dey" → should be flagged
    assert pidgin_flags[0] is True
    # Second line is plain English → not flagged
    assert pidgin_flags[1] is False


def test_normalize_fallback_on_llm_error():
    """If the LLM raises, normalize should fall back to raw lines."""
    class BrokenLLM:
        name = "broken"
        def complete(self, prompt, system=""):
            raise ConnectionError("network error")

    lyrics = RawLyrics(raw_text="line one\nline two", source="test")
    normalized = normalize_lyrics(lyrics, llm=BrokenLLM())
    assert len(normalized) == 2
    assert normalized[0].cleaned_line == "line one"
