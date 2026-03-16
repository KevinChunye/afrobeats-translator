"""
Stage 3: Nigerian lyric intelligence — normalization & slang detection.

This is the most culturally-sensitive stage of the pipeline. The LLM is asked to:
  1. Rewrite noisy / pidgin-heavy lines into a cleaned intermediate form.
  2. Flag lines that are slang-heavy or pidgin-heavy.
  3. Identify ambiguous phrases.
  4. Preserve line-by-line alignment.

The output is a list of (original_line, cleaned_line, is_pidgin, ambiguous_phrases).
Translation and explanation happen in separate stages so the pipeline remains modular.

Custom glossary support:
  Pass a `glossary` dict of {term: meaning} to `normalize_lyrics()` and it will be
  injected into the prompt so the LLM can prioritise your definitions over generic ones.
  This is where you'd plug in a fine-tuned or domain-specific model later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..logger import get_logger
from ..models import RawLyrics
from ..providers.llm_provider import LLMProvider, build_llm_provider
from ..utils.text import chunk_lines, safe_json_parse

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are an expert in Nigerian English, Nigerian Pidgin (Naija), Yoruba, Igbo, \
and contemporary Afrobeats / Amapiano slang. \
You help non-Nigerian listeners understand song lyrics.

Your job in this stage is NORMALIZATION only — not full translation.
For each lyric line you will:
1. Produce a "cleaned_line": rewrite the line in cleaner English while preserving \
   the original meaning, Nigerian idioms, and feel. Do not fully translate yet — \
   keep recognisable Nigerian phrases but fix transcription errors and unclear words.
2. Decide "is_pidgin_heavy": true if the line is heavily Pidgin or slang-laden.
3. List "ambiguous_phrases": up to 3 phrases you are uncertain about.

Return a JSON array, one object per input line, in this exact schema:
[
  {
    "original_line": "<original>",
    "cleaned_line": "<cleaned>",
    "is_pidgin_heavy": true/false,
    "ambiguous_phrases": ["phrase1", "phrase2"]
  },
  ...
]
Respond with ONLY the JSON array. No markdown fences, no commentary.
"""


@dataclass
class NormalizedLine:
    original_line: str
    cleaned_line: str
    is_pidgin_heavy: bool
    ambiguous_phrases: list[str]


def _build_user_prompt(lines: list[str], glossary: dict[str, str] | None = None) -> str:
    glossary_block = ""
    if glossary:
        items = "\n".join(f"  {k}: {v}" for k, v in glossary.items())
        glossary_block = f"\nCustom glossary (use these definitions):\n{items}\n"

    lines_block = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))
    return f"{glossary_block}\nLyric lines to normalize:\n{lines_block}"


def normalize_lyrics(
    raw_lyrics: RawLyrics,
    llm: LLMProvider | None = None,
    glossary: dict[str, str] | None = None,
    chunk_size: int = 20,
) -> list[NormalizedLine]:
    """
    Normalize all lines in raw_lyrics using the LLM.
    Processes lines in chunks to stay within token limits.
    Falls back gracefully if LLM is unavailable.
    """
    provider = llm or build_llm_provider()
    lines = raw_lyrics.lines
    if not lines:
        return []

    results: list[NormalizedLine] = []

    for chunk in chunk_lines(lines, chunk_size):
        prompt = _build_user_prompt(chunk, glossary)
        try:
            raw_response = provider.complete(prompt=prompt, system=SYSTEM_PROMPT)
            parsed = safe_json_parse(raw_response)
            if not isinstance(parsed, list):
                raise ValueError("Expected JSON array from normalization LLM")

            for item in parsed:
                results.append(
                    NormalizedLine(
                        original_line=item.get("original_line", ""),
                        cleaned_line=item.get("cleaned_line", item.get("original_line", "")),
                        is_pidgin_heavy=bool(item.get("is_pidgin_heavy", False)),
                        ambiguous_phrases=item.get("ambiguous_phrases", []),
                    )
                )
        except Exception as exc:
            logger.warning(f"Normalization LLM call failed: {exc}. Using raw lines as fallback.")
            for line in chunk:
                results.append(
                    NormalizedLine(
                        original_line=line,
                        cleaned_line=line,
                        is_pidgin_heavy=False,
                        ambiguous_phrases=[],
                    )
                )

    return results
