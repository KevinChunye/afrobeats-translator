"""
Stage 1 (audio path): Optionally isolate vocals from an audio file.
"""

from __future__ import annotations

from ..logger import get_logger
from ..providers.audio_isolation_provider import build_isolation_provider

logger = get_logger(__name__)


def preprocess_audio(
    audio_path: str,
    isolation_provider_name: str | None = None,
) -> str:
    """
    Attempt vocal isolation. Returns path to processed audio file.
    If isolation fails or is skipped, returns the original path.
    """
    provider = build_isolation_provider(isolation_provider_name)
    try:
        result = provider.isolate_vocals(audio_path)
        logger.info(f"Audio preprocessing complete → {result}")
        return result
    except (NotImplementedError, RuntimeError) as exc:
        logger.warning(f"Vocal isolation skipped: {exc}")
        return audio_path
