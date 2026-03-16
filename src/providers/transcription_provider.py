"""
Transcription provider abstractions.

Implementations:
  - OpenAIWhisperProvider   — uses OpenAI Whisper API (recommended, works well
                              with mixed-language African music)
  - GoogleSpeechProvider    — stub using Google Cloud Speech-to-Text
                              TODO: full implementation requires google-cloud-speech
                              and a service-account JSON
  - StubTranscriptionProvider — returns canned text; no API needed

TODO: Consider adding a local Whisper option via `openai-whisper` package for
      fully offline transcription.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..config import get_settings
from ..logger import get_logger
from ..models import RawTranscript, TranscriptSegment

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# OpenAI Whisper (cloud)
# ---------------------------------------------------------------------------


class OpenAIWhisperProvider:
    """
    Transcribes audio using the OpenAI Whisper API endpoint.
    Handles mixed-language content reasonably well.
    """

    name = "openai_whisper"

    def __init__(self) -> None:
        self._client = self._build_client()

    def _build_client(self):  # type: ignore[return]
        try:
            from openai import OpenAI

            key = get_settings().openai_api_key
            if not key:
                logger.warning("OPENAI_API_KEY not set – OpenAIWhisperProvider unavailable")
                return None
            return OpenAI(api_key=key)
        except ImportError:
            logger.warning("openai package not installed")
            return None

    def transcribe(self, audio_path: str) -> RawTranscript:
        if self._client is None:
            raise RuntimeError("OpenAI Whisper client not initialised")

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing {path.name} via OpenAI Whisper…")
        with open(path, "rb") as f:
            response = self._client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                # Hint the model about Nigerian/West African context
                prompt=(
                    "This is an Afrobeats or Amapiano song with Nigerian English, "
                    "Pidgin English, Yoruba, and Igbo phrases mixed in."
                ),
            )

        segments = []
        raw_segments = getattr(response, "segments", None) or []
        for seg in raw_segments:
            segments.append(
                TranscriptSegment(
                    start_sec=seg.get("start", 0.0),
                    end_sec=seg.get("end", 0.0),
                    text=seg.get("text", "").strip(),
                    confidence=seg.get("avg_logprob", 0.0),
                )
            )

        full_text = getattr(response, "text", "") or ""
        if not segments and full_text:
            segments = [TranscriptSegment(start_sec=0.0, end_sec=0.0, text=full_text)]

        return RawTranscript(
            segments=segments,
            language_detected=getattr(response, "language", None),
            full_text=full_text,
        )


# ---------------------------------------------------------------------------
# Google Speech-to-Text (stub — requires google-cloud-speech)
# ---------------------------------------------------------------------------


class GoogleSpeechProvider:
    """
    TODO: Full implementation requires:
      1. pip install google-cloud-speech
      2. GOOGLE_APPLICATION_CREDENTIALS env var pointing to a service-account JSON
         OR use the GOOGLE_API_KEY with the REST endpoint.
      3. Audio must be LINEAR16 or FLAC; MP3 requires transcoding first.

    The Nigerian English BCP-47 tag is "en-NG".
    Docs: https://cloud.google.com/speech-to-text/docs
    """

    name = "google"

    def __init__(self) -> None:
        logger.warning(
            "GoogleSpeechProvider is a stub. "
            "See TODO in src/providers/transcription_provider.py for setup instructions."
        )

    def transcribe(self, audio_path: str) -> RawTranscript:
        # TODO: Implement using google-cloud-speech SDK
        # Example sketch:
        #   from google.cloud import speech
        #   client = speech.SpeechClient()
        #   with open(audio_path, "rb") as f:
        #       audio = speech.RecognitionAudio(content=f.read())
        #   config = speech.RecognitionConfig(
        #       encoding=speech.RecognitionConfig.AudioEncoding.MP3,
        #       language_code="en-NG",
        #       alternative_language_codes=["yo", "ig", "pcm"],
        #   )
        #   response = client.recognize(config=config, audio=audio)
        raise NotImplementedError(
            "GoogleSpeechProvider is not yet implemented. "
            "Use OpenAIWhisperProvider or StubTranscriptionProvider instead."
        )


# ---------------------------------------------------------------------------
# Stub (offline, for testing)
# ---------------------------------------------------------------------------


class StubTranscriptionProvider:
    name = "stub"

    def transcribe(self, audio_path: str) -> RawTranscript:
        logger.warning(
            "StubTranscriptionProvider: returning canned transcript. "
            "Configure a real transcription provider for production use."
        )
        stub_text = (
            "Omo, your waist dey sweet my eye\n"
            "E be like say na God send you come\n"
            "Baby girl, you dey make me feel alive\n"
            "I no go let you go, no cap\n"
        )
        lines = stub_text.strip().splitlines()
        segments = [
            TranscriptSegment(start_sec=i * 4.0, end_sec=(i + 1) * 4.0, text=line)
            for i, line in enumerate(lines)
        ]
        return RawTranscript(segments=segments, language_detected="en-NG", full_text=stub_text)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_transcription_provider(provider_name: str | None = None):
    settings = get_settings()
    name = provider_name or settings.transcription.provider

    if name == "openai_whisper":
        p = OpenAIWhisperProvider()
        if p._client:
            return p
        logger.warning("OpenAI Whisper unavailable, falling back to stub")
        return StubTranscriptionProvider()

    if name == "google":
        return GoogleSpeechProvider()

    return StubTranscriptionProvider()
