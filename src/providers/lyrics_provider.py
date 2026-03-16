"""
Lyrics provider abstractions.

Implementations:
  - MockLyricsProvider     — returns sample data; always works, no API needed
  - GeniusLyricsProvider   — scrapes Genius via lyricsgenius (TODO: optional dep)
  - ManualLyricsProvider   — wraps user-supplied raw text

The factory `build_lyrics_provider()` returns the best available backend.

TODO: Integrate a dedicated lyrics API (e.g. Genius, AZLyrics, Musixmatch).
      Genius requires a free client access token at https://genius.com/api-clients
      and the `lyricsgenius` pip package.
"""

from __future__ import annotations

import abc
from typing import Protocol

from ..logger import get_logger
from ..models import RawLyrics

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class LyricsProvider(Protocol):
    def fetch(self, song_title: str, artist: str) -> RawLyrics:
        ...

    @property
    def name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# Mock / sample data (always available)
# ---------------------------------------------------------------------------

_MOCK_LYRICS = {
    ("essence", "wizkid"): """\
You don cast your spell on me, can't explain it
Your waist, your eyes, your thighs got me
Baby girl, you sweet like agbalumo
You dey make my body vibrate, e dey do me
Come make we fall in love, e go sweet
No cap, you be the finest thing wey I don see
I wan love you down, I wan make you mine
Baby, you dey make me feel sublime
Jah bless the day wey I meet you
E be like say na God arrange am
""",
    ("fall", "davido"): """\
I cannot explain it
Boy, I'm in love again
Won't let you fall, my baby
I just wanna see you smile
Omo, your love dey make me craze
You sabi how to do am, e dey sweet my face
No shakara, come closer
Make I look into your eyes, your eyes
I don dey feel this thing since forever
Baby girl, you be my everything
""",
    ("no wahala", "1da banton"): """\
She no get wahala, she no get drama
Every time she dey smile, e dey calm my trauma
She be the realest, she be my Madonna
I go love her well well, I no go dishonour
No wahala, no wahala
This girl dey make sense, she no dey cause palava
She cook for me, she pray for me, she sabi the saga
Omo, from Lagos to Kampala she be my sensor
Every night I thank God say e send her
She don enter my heart, she be the answer
Wahala don finish since I find her
I wan put ring for her finger
Make she know say she be my forever
No cap, this love go last till manana
""",
}


class MockLyricsProvider:
    name = "mock"

    def fetch(self, song_title: str, artist: str) -> RawLyrics:
        key = (song_title.lower().strip(), artist.lower().strip())
        text = _MOCK_LYRICS.get(key)
        if text:
            logger.info(f"Mock lyrics found for '{song_title}' by {artist}")
            return RawLyrics(
                song_title=song_title,
                artist=artist,
                raw_text=text.strip(),
                source="mock",
            )
        # Generic placeholder when song not in mock DB
        logger.warning(
            f"No mock lyrics for '{song_title}' by {artist}. Returning placeholder."
        )
        placeholder = (
            f"[Placeholder lyrics for '{song_title}' by {artist}]\n"
            "Omo, this song na vibes\n"
            "E dey sweet my ear, no cap\n"
            "Wahala dey but we dey here\n"
            "Na so e be, my brother\n"
        )
        return RawLyrics(
            song_title=song_title,
            artist=artist,
            raw_text=placeholder,
            source="mock_placeholder",
        )


# ---------------------------------------------------------------------------
# Manual / user-supplied
# ---------------------------------------------------------------------------


class ManualLyricsProvider:
    name = "manual"

    def __init__(self, raw_text: str) -> None:
        self._text = raw_text

    def fetch(self, song_title: str = "", artist: str = "") -> RawLyrics:
        return RawLyrics(
            song_title=song_title or "Unknown",
            artist=artist or "Unknown",
            raw_text=self._text,
            source="user_provided",
        )


# ---------------------------------------------------------------------------
# Genius (optional — requires `lyricsgenius` + GENIUS_ACCESS_TOKEN)
# ---------------------------------------------------------------------------


class GeniusLyricsProvider:
    """
    Fetches lyrics from Genius.

    TODO: Set GENIUS_ACCESS_TOKEN in your environment.
          Install: pip install lyricsgenius
          Genius API docs: https://docs.genius.com
    """

    name = "genius"

    def __init__(self) -> None:
        self._client = self._build_client()

    def _build_client(self):  # type: ignore[return]
        try:
            import lyricsgenius
            import os

            token = os.getenv("GENIUS_ACCESS_TOKEN", "")
            if not token:
                logger.warning("GENIUS_ACCESS_TOKEN not set – GeniusLyricsProvider unavailable")
                return None
            return lyricsgenius.Genius(token, skip_non_songs=True, excluded_terms=["(Remix)"])
        except ImportError:
            logger.warning("lyricsgenius not installed. `pip install lyricsgenius` to enable.")
            return None

    def fetch(self, song_title: str, artist: str) -> RawLyrics:
        if self._client is None:
            raise RuntimeError("Genius client not available")
        song = self._client.search_song(song_title, artist)
        if song is None:
            raise ValueError(f"Song '{song_title}' by '{artist}' not found on Genius")
        return RawLyrics(
            song_title=song_title,
            artist=artist,
            raw_text=song.lyrics,
            source="genius",
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_lyrics_provider(prefer_real: bool = True) -> LyricsProvider:
    """Return Genius if available, otherwise fall back to Mock."""
    if prefer_real:
        try:
            provider = GeniusLyricsProvider()
            if provider._client is not None:
                return provider
        except Exception:
            pass
    logger.info("Using MockLyricsProvider (no real lyrics API configured)")
    return MockLyricsProvider()
