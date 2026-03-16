"""
Pydantic data models for the entire pipeline.
These are the canonical data contracts between pipeline stages.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InputMode(str, Enum):
    LYRICS_SONG = "lyrics_song"      # title + artist -> fetch lyrics
    LYRICS_TEXT = "lyrics_text"      # raw text provided directly
    AUDIO_FILE = "audio_file"        # local audio file


class PipelineInput(BaseModel):
    mode: InputMode
    song_title: str | None = None
    artist: str | None = None
    raw_lyrics: str | None = None
    audio_file_path: str | None = None
    output_formats: list[str] = Field(default_factory=lambda: ["console"])
    output_file: str | None = None


class RawLyrics(BaseModel):
    song_title: str | None = None
    artist: str | None = None
    raw_text: str
    source: str = "unknown"   # e.g. "genius", "user_provided", "mock"
    lines: list[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.lines and self.raw_text:
            self.lines = [
                line.strip()
                for line in self.raw_text.splitlines()
                if line.strip()
            ]


class TranscriptSegment(BaseModel):
    start_sec: float
    end_sec: float
    text: str
    confidence: float = 1.0


class RawTranscript(BaseModel):
    segments: list[TranscriptSegment]
    language_detected: str | None = None
    full_text: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.full_text and self.segments:
            self.full_text = " ".join(s.text for s in self.segments)


class LineTranslation(BaseModel):
    """Translation result for a single lyric line."""

    line_number: int
    original_line: str
    cleaned_line: str = ""
    translation_literal: str = ""
    translation_natural: str = ""
    slang_explanation: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: str = ""
    is_pidgin_heavy: bool = False
    ambiguous_phrases: list[str] = Field(default_factory=list)


class SongSummary(BaseModel):
    """High-level summary of the song."""

    main_theme: str = ""
    emotional_tone: str = ""
    recurring_slang: list[str] = Field(default_factory=list)
    plain_english_summary: str = ""
    language_mix: list[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """Final output from the full pipeline."""

    song_title: str | None = None
    artist: str | None = None
    input_mode: InputMode
    line_translations: list[LineTranslation] = Field(default_factory=list)
    song_summary: SongSummary = Field(default_factory=SongSummary)
    raw_lyrics_source: str = ""
    processing_notes: list[str] = Field(default_factory=list)
    error: str | None = None
