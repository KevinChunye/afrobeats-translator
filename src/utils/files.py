"""File system helpers."""

from __future__ import annotations

from pathlib import Path


SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}


def validate_audio_file(path: str) -> Path:
    """Raise ValueError with a clear message if the audio file is unusable."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    if p.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(
            f"Unsupported audio format: {p.suffix}. "
            f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
        )
    return p


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_text_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Text file not found: {path}")
    return p.read_text(encoding="utf-8")
