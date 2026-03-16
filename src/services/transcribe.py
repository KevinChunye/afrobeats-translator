"""
Stage 2 (audio path): Transcribe processed audio to text.
"""

from __future__ import annotations

from ..logger import get_logger
from ..models import RawLyrics, RawTranscript
from ..providers.transcription_provider import build_transcription_provider

logger = get_logger(__name__)


def transcribe_audio(
    audio_path: str,
    provider_name: str | None = None,
) -> RawTranscript:
    """Transcribe the given audio file and return a RawTranscript."""
    provider = build_transcription_provider(provider_name)
    logger.info(f"Transcribing audio with provider: {provider.name}")
    return provider.transcribe(audio_path)


def transcript_to_raw_lyrics(
    transcript: RawTranscript,
    song_title: str | None = None,
    artist: str | None = None,
) -> RawLyrics:
    """Convert a RawTranscript into a RawLyrics for downstream pipeline stages."""
    return RawLyrics(
        song_title=song_title,
        artist=artist,
        raw_text=transcript.full_text,
        source="transcription",
        lines=[seg.text for seg in transcript.segments if seg.text.strip()],
    )
