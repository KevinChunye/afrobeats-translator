"""
Vocal isolation / audio stem separation provider abstractions.

Implementations:
  - DemucsIsolationProvider   — uses Facebook's Demucs locally (offline, high quality)
                                TODO: `pip install demucs` and torch
  - ElevenLabsIsolationProvider — stub; ElevenLabs v1 API does not expose a public
                                   vocal isolation endpoint as of 2025. This is a
                                   placeholder for a future capability.
                                   TODO: Monitor https://elevenlabs.io/docs for updates.
  - StubIsolationProvider     — passes audio through unchanged; always available

Design note: Vocal isolation is optional. If unavailable, the pipeline proceeds
with the raw audio file and transcription quality may be lower.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..config import get_settings
from ..logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Demucs (local, CPU/GPU)
# ---------------------------------------------------------------------------


class DemucsIsolationProvider:
    """
    Separates vocals from accompaniment using Facebook's Demucs model.

    Requirements:
      pip install demucs
      (torch is installed automatically as a dependency)

    Usage produces a directory:
      separated/htdemucs/<stem>/<track-name>/vocals.wav

    TODO: Make model name configurable (htdemucs, htdemucs_ft, mdx_extra, etc.)
    TODO: Add GPU support detection.
    """

    name = "demucs"

    def __init__(self, output_dir: str = "output/stems") -> None:
        self._output_dir = Path(output_dir)
        self._available = self._check_available()

    def _check_available(self) -> bool:
        try:
            import demucs  # noqa: F401

            return True
        except ImportError:
            logger.warning("demucs not installed. `pip install demucs` to enable vocal isolation.")
            return False

    def isolate_vocals(self, audio_path: str) -> str:
        """Return path to isolated vocals wav file."""
        if not self._available:
            raise RuntimeError("Demucs is not installed")

        import subprocess

        self._output_dir.mkdir(parents=True, exist_ok=True)
        input_path = Path(audio_path)

        logger.info(f"Running Demucs on {input_path.name}…")
        result = subprocess.run(
            [
                "python", "-m", "demucs",
                "--two-stems", "vocals",
                "-o", str(self._output_dir),
                str(input_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Demucs failed:\n{result.stderr}")

        # Demucs writes to: <output_dir>/htdemucs/<filename_stem>/vocals.wav
        vocals_path = self._output_dir / "htdemucs" / input_path.stem / "vocals.wav"
        if not vocals_path.exists():
            raise FileNotFoundError(f"Demucs output not found at {vocals_path}")

        logger.info(f"Vocals isolated → {vocals_path}")
        return str(vocals_path)


# ---------------------------------------------------------------------------
# ElevenLabs (stub — API endpoint not publicly available as of 2025)
# ---------------------------------------------------------------------------


class ElevenLabsIsolationProvider:
    """
    TODO: ElevenLabs offers audio isolation via their Sound Effects / Voice Isolation
          product in the web app, but no public REST endpoint is documented as of
          early 2025.

          When this becomes available:
          1. Set ELEVENLABS_API_KEY in your environment.
          2. Wire up requests to https://api.elevenlabs.io/v1/audio-isolation
             (endpoint path is speculative — verify from official docs)
          3. Handle audio upload, poll for completion, download result.

    For now, this class raises NotImplementedError.
    """

    name = "elevenlabs"

    def __init__(self) -> None:
        key = get_settings().elevenlabs_api_key
        if not key:
            logger.warning("ELEVENLABS_API_KEY not set")
        logger.warning(
            "ElevenLabsIsolationProvider is a stub. "
            "See TODO in src/providers/audio_isolation_provider.py."
        )

    def isolate_vocals(self, audio_path: str) -> str:
        raise NotImplementedError(
            "ElevenLabs vocal isolation is not yet implemented. "
            "Use DemucsIsolationProvider or StubIsolationProvider instead."
        )


# ---------------------------------------------------------------------------
# Stub (no-op, just returns original file)
# ---------------------------------------------------------------------------


class StubIsolationProvider:
    """
    Pass-through provider: returns the original audio file unchanged.
    Transcription quality will depend on how clean the original audio is.
    """

    name = "stub"

    def isolate_vocals(self, audio_path: str) -> str:
        logger.warning(
            "StubIsolationProvider: skipping vocal isolation. "
            "Transcription will use raw audio."
        )
        return audio_path


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_isolation_provider(provider_name: str | None = None):
    settings = get_settings()
    name = provider_name or settings.audio.isolation_provider

    if name == "demucs":
        p = DemucsIsolationProvider()
        if p._available:
            return p
        logger.warning("Demucs unavailable, falling back to stub isolation")
        return StubIsolationProvider()

    if name == "elevenlabs":
        return ElevenLabsIsolationProvider()

    return StubIsolationProvider()
