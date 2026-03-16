"""
Stage 4: Line-by-line translation.

Takes the normalized lines and produces:
  - translation_literal  : word-for-word / close translation
  - translation_natural  : idiomatic plain English (what a native speaker would say)
  - confidence           : 0.0–1.0 self-assessment from the LLM
  - slang_explanation    : brief in-line gloss of key slang terms
  - notes                : any extra cultural or linguistic context

Prompt engineering principles applied here:
  - Prefer meaning over literal translation.
  - Preserve idioms where possible; explain them in slang_explanation.
  - Clearly mark uncertainty with low confidence and notes.
  - Avoid overclaiming on ambiguous lines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..logger import get_logger
from ..models import LineTranslation
from ..providers.llm_provider import LLMProvider, build_llm_provider
from ..services.normalize import NormalizedLine
from ..utils.text import chunk_list, safe_json_parse

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are a bilingual expert in Nigerian English, Nigerian Pidgin (Naija), Yoruba, \
Igbo, and contemporary Afrobeats / Amapiano culture. \
You translate lyric lines for an international audience who loves African music \
but may not know the slang.

For each lyric line you receive, produce:
1. "translation_literal" : a close, word-for-word English rendering
2. "translation_natural" : what a native English speaker would naturally say — \
   prioritise meaning and feel over literal accuracy
3. "confidence" : a float 0.0–1.0 reflecting how certain you are (be honest; \
   use 0.5 or below for ambiguous lines)
4. "slang_explanation" : a short plain-English gloss of any slang, Pidgin, or \
   Nigerian idioms in the line (empty string if none)
5. "notes" : any cultural context, wordplay, or double meanings worth noting \
   (empty string if nothing significant)

Critical rules:
- NEVER fabricate a meaning for a phrase you don't know — instead lower confidence \
  and note the uncertainty.
- Preserve wordplay and cultural references; explain them in notes.
- If a line is already standard English, just echo it with high confidence.

Return a JSON array aligned 1-to-1 with the input lines, schema:
[
  {
    "translation_literal": "...",
    "translation_natural": "...",
    "confidence": 0.85,
    "slang_explanation": "...",
    "notes": "..."
  },
  ...
]
Respond with ONLY the JSON array. No markdown fences, no commentary.
"""


def _build_user_prompt(normalized_lines: list[NormalizedLine]) -> str:
    entries = []
    for i, nl in enumerate(normalized_lines):
        entries.append(
            f"{i + 1}. original: {nl.original_line!r}\n"
            f"   cleaned:  {nl.cleaned_line!r}"
        )
    return "Translate these lyric lines:\n\n" + "\n\n".join(entries)


def translate_lines(
    normalized_lines: list[NormalizedLine],
    llm: LLMProvider | None = None,
    chunk_size: int = 15,
) -> list[LineTranslation]:
    """
    Translate a list of NormalizedLine objects into LineTranslation objects.
    Processes in chunks; falls back gracefully on error.
    """
    provider = llm or build_llm_provider()
    all_results: list[LineTranslation] = []

    # We need to track the global line number across chunks
    global_index = 0

    for chunk in chunk_list(normalized_lines, chunk_size):
        prompt = _build_user_prompt(chunk)
        try:
            raw = provider.complete(prompt=prompt, system=SYSTEM_PROMPT)
            parsed = safe_json_parse(raw)
            if not isinstance(parsed, list):
                raise ValueError("Expected JSON array from translation LLM")

            for i, (nl, item) in enumerate(zip(chunk, parsed)):
                all_results.append(
                    LineTranslation(
                        line_number=global_index + i + 1,
                        original_line=nl.original_line,
                        cleaned_line=nl.cleaned_line,
                        translation_literal=item.get("translation_literal", ""),
                        translation_natural=item.get("translation_natural", ""),
                        confidence=float(item.get("confidence", 1.0)),
                        slang_explanation=item.get("slang_explanation", ""),
                        notes=item.get("notes", ""),
                        is_pidgin_heavy=nl.is_pidgin_heavy,
                        ambiguous_phrases=nl.ambiguous_phrases,
                    )
                )
        except Exception as exc:
            logger.warning(f"Translation LLM call failed: {exc}. Using fallback for chunk.")
            for i, nl in enumerate(chunk):
                all_results.append(
                    LineTranslation(
                        line_number=global_index + i + 1,
                        original_line=nl.original_line,
                        cleaned_line=nl.cleaned_line,
                        translation_literal=nl.cleaned_line,
                        translation_natural=nl.cleaned_line,
                        confidence=0.0,
                        slang_explanation="",
                        notes="Translation unavailable (LLM error)",
                        is_pidgin_heavy=nl.is_pidgin_heavy,
                        ambiguous_phrases=nl.ambiguous_phrases,
                    )
                )

        global_index += len(chunk)

    return all_results
