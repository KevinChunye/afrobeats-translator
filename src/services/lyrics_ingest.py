"""
Stage 1 (lyrics path): Ingest lyrics from a provider or raw text.
"""

from __future__ import annotations

from ..logger import get_logger
from ..models import PipelineInput, RawLyrics, InputMode
from ..providers.lyrics_provider import (
    LyricsProvider,
    ManualLyricsProvider,
    build_lyrics_provider,
)

logger = get_logger(__name__)


def ingest_lyrics(pipeline_input: PipelineInput, provider: LyricsProvider | None = None) -> RawLyrics:
    """
    Given a PipelineInput, return a RawLyrics object.

    - LYRICS_TEXT mode: wrap the raw text directly.
    - LYRICS_SONG mode: delegate to the configured lyrics provider.
    """
    if pipeline_input.mode == InputMode.LYRICS_TEXT:
        if not pipeline_input.raw_lyrics:
            raise ValueError("raw_lyrics must be set when mode is LYRICS_TEXT")
        logger.info("Ingesting user-provided lyrics text")
        return ManualLyricsProvider(pipeline_input.raw_lyrics).fetch(
            song_title=pipeline_input.song_title or "",
            artist=pipeline_input.artist or "",
        )

    if pipeline_input.mode == InputMode.LYRICS_SONG:
        if not pipeline_input.song_title or not pipeline_input.artist:
            raise ValueError("song_title and artist must be set when mode is LYRICS_SONG")
        p = provider or build_lyrics_provider()
        logger.info(f"Fetching lyrics for '{pipeline_input.song_title}' by {pipeline_input.artist}")
        return p.fetch(pipeline_input.song_title, pipeline_input.artist)

    raise ValueError(f"ingest_lyrics called with unsupported mode: {pipeline_input.mode}")
