"""
Stage 5: Song-level explanation and summary.

After translating individual lines, this stage zooms out and produces a holistic
summary of the song:
  - main theme
  - emotional tone
  - recurring slang / motifs
  - plain-English explanation of what the song is about
  - language mix detected
"""

from __future__ import annotations

from ..logger import get_logger
from ..models import LineTranslation, SongSummary
from ..providers.llm_provider import LLMProvider, build_llm_provider
from ..utils.text import safe_json_parse

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are a music analyst and cultural expert specialising in Afrobeats and Amapiano.
Given the translated lyrics of a song, produce a concise song-level analysis.

Return a single JSON object with these keys:
{
  "main_theme": "<1-2 sentences about the central topic of the song>",
  "emotional_tone": "<e.g. joyful, melancholic, romantic, hype, introspective>",
  "recurring_slang": ["<slang term 1>", "<slang term 2>", ...],
  "plain_english_summary": "<3-5 sentence plain English explanation of what the song \
is about, what the artist is expressing, and why it resonates>",
  "language_mix": ["<language/dialect 1>", "<language/dialect 2>", ...]
}
Respond with ONLY the JSON object. No markdown fences, no commentary.
"""


def _build_prompt(
    song_title: str | None,
    artist: str | None,
    line_translations: list[LineTranslation],
) -> str:
    header = ""
    if song_title:
        header = f"Song: {song_title}"
    if artist:
        header += f" by {artist}"
    if header:
        header += "\n\n"

    pairs = []
    for lt in line_translations:
        pairs.append(
            f"  Original: {lt.original_line}\n"
            f"  Translation: {lt.translation_natural or lt.translation_literal}"
        )

    return header + "Translated lyrics:\n\n" + "\n\n".join(pairs)


def generate_song_summary(
    song_title: str | None,
    artist: str | None,
    line_translations: list[LineTranslation],
    llm: LLMProvider | None = None,
) -> SongSummary:
    """Generate a SongSummary from the translated line data."""
    provider = llm or build_llm_provider()
    prompt = _build_prompt(song_title, artist, line_translations)

    try:
        raw = provider.complete(prompt=prompt, system=SYSTEM_PROMPT)
        parsed = safe_json_parse(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object from explanation LLM")

        return SongSummary(
            main_theme=parsed.get("main_theme", ""),
            emotional_tone=parsed.get("emotional_tone", ""),
            recurring_slang=parsed.get("recurring_slang", []),
            plain_english_summary=parsed.get("plain_english_summary", ""),
            language_mix=parsed.get("language_mix", []),
        )
    except Exception as exc:
        logger.warning(f"Song summary LLM call failed: {exc}. Returning empty summary.")
        return SongSummary(
            main_theme="Summary unavailable",
            plain_english_summary=f"Could not generate summary: {exc}",
        )
