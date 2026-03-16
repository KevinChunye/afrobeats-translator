"""
Lyrics provider abstractions.

Provider chain (best → fallback):
  1. GeniusLyricsProvider   — best coverage; needs GENIUS_ACCESS_TOKEN + lyricsgenius
  2. LyricsOvhProvider      — free public API, no key, good Afrobeats coverage ✅
  3. MockLyricsProvider     — hardcoded demo songs; CLI testing only

The factory always tries LyricsOvh first (no setup needed) so ANY song works
out of the box for the web UI.
"""

from __future__ import annotations

from typing import Protocol
from urllib.parse import quote

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
# lyrics.ovh — free public API, no key required
# ---------------------------------------------------------------------------


class LyricsOvhProvider:
    """
    Fetches lyrics from lyrics.ovh — a free, open API with no authentication.
    Good coverage of mainstream and Afrobeats artists.

    API: GET https://api.lyrics.ovh/v1/{artist}/{title}
    Docs: https://lyricsovh.docs.apiary.io/

    Raises ValueError (song not found) or RuntimeError (network error).
    The pipeline catches both and surfaces a user-friendly message.
    """

    name = "lyrics.ovh"
    _BASE = "https://api.lyrics.ovh/v1"

    def fetch(self, song_title: str, artist: str) -> RawLyrics:
        import requests

        url = f"{self._BASE}/{quote(artist)}/{quote(song_title)}"
        logger.info(f"Fetching lyrics from lyrics.ovh: {url}")

        try:
            resp = requests.get(url, timeout=12)
        except requests.RequestException as exc:
            raise RuntimeError(f"lyrics.ovh network error: {exc}")

        if resp.status_code == 404:
            raise ValueError(
                f'Lyrics not found for "{song_title}" by "{artist}". '
                "Try the 'Paste lyrics' option below the search box."
            )
        resp.raise_for_status()

        lyrics_text = resp.json().get("lyrics", "").strip()
        if not lyrics_text:
            raise ValueError(
                f'Empty lyrics returned for "{song_title}" by "{artist}". '
                "Try pasting the lyrics directly."
            )

        return RawLyrics(
            song_title=song_title,
            artist=artist,
            raw_text=lyrics_text,
            source="lyrics.ovh",
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
    """
    Return the best available lyrics provider.

    Chain: Genius (if token set) → lyrics.ovh (free, default) → Mock (CLI fallback)
    """
    if prefer_real:
        # Genius: best quality, requires token
        try:
            genius = GeniusLyricsProvider()
            if genius._client is not None:
                logger.info("Using GeniusLyricsProvider")
                return genius
        except Exception:
            pass

        # lyrics.ovh: free, no key, works for most mainstream + Afrobeats songs
        logger.info("Using LyricsOvhProvider (free, no API key required)")
        return LyricsOvhProvider()

    logger.info("Using MockLyricsProvider (offline/CLI mode)")
    return MockLyricsProvider()
