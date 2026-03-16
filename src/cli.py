"""
CLI interface for afrobeats-translator.

Commands:
  translate-song    — song title + artist → fetch lyrics → translate
  translate-lyrics  — raw lyrics file → translate
  translate-audio   — audio file → transcribe → translate
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .config import get_settings
from .logger import configure_level, get_logger
from .models import InputMode, PipelineInput
from .pipeline import run_and_format

app = typer.Typer(
    name="afrobeats-translator",
    help="Translate Afrobeats / Amapiano lyrics from Nigerian English / Pidgin to plain English.",
    add_completion=False,
)
console = Console()
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared options (injected via typer.Option)
# ---------------------------------------------------------------------------

_OUTPUT_HELP = "Output format(s). Comma-separated: console,json,markdown"
_FILE_HELP = "Output file path (for json/markdown modes)"
_VERBOSE_HELP = "Enable debug logging"
_LLM_HELP = "LLM provider: anthropic | openai | deepseek"


def _parse_formats(raw: str) -> list[str]:
    return [f.strip().lower() for f in raw.split(",") if f.strip()]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("translate-song")
def translate_song(
    song: str = typer.Option(..., "--song", "-s", help="Song title"),
    artist: str = typer.Option(..., "--artist", "-a", help="Artist name"),
    output: str = typer.Option("console", "--output", "-o", help=_OUTPUT_HELP),
    output_file: Optional[str] = typer.Option(None, "--output-file", "-f", help=_FILE_HELP),
    llm_provider: Optional[str] = typer.Option(None, "--llm", help=_LLM_HELP),
    verbose: bool = typer.Option(False, "--verbose", "-v", help=_VERBOSE_HELP),
) -> None:
    """Translate a song by fetching its lyrics from a lyrics provider."""
    if verbose:
        configure_level("DEBUG")

    _maybe_override_llm(llm_provider)

    pi = PipelineInput(
        mode=InputMode.LYRICS_SONG,
        song_title=song,
        artist=artist,
        output_formats=_parse_formats(output),
        output_file=output_file,
    )
    result = run_and_format(pi)
    if result.error:
        raise typer.Exit(code=1)


@app.command("translate-lyrics")
def translate_lyrics(
    input_file: Optional[str] = typer.Option(None, "--input-file", "-i", help="Path to lyrics text file"),
    lyrics: Optional[str] = typer.Option(None, "--lyrics", "-l", help="Inline lyrics string"),
    song: Optional[str] = typer.Option(None, "--song", "-s", help="Song title (optional metadata)"),
    artist: Optional[str] = typer.Option(None, "--artist", "-a", help="Artist name (optional metadata)"),
    output: str = typer.Option("console", "--output", "-o", help=_OUTPUT_HELP),
    output_file: Optional[str] = typer.Option(None, "--output-file", "-f", help=_FILE_HELP),
    llm_provider: Optional[str] = typer.Option(None, "--llm", help=_LLM_HELP),
    verbose: bool = typer.Option(False, "--verbose", "-v", help=_VERBOSE_HELP),
) -> None:
    """Translate lyrics provided as a text file or inline string."""
    if verbose:
        configure_level("DEBUG")

    if not input_file and not lyrics:
        console.print("[red]Error:[/red] Provide --input-file or --lyrics")
        raise typer.Exit(code=1)

    raw_text: str
    if input_file:
        p = Path(input_file)
        if not p.exists():
            console.print(f"[red]Error:[/red] File not found: {input_file}")
            raise typer.Exit(code=1)
        raw_text = p.read_text(encoding="utf-8")
    else:
        raw_text = lyrics  # type: ignore[assignment]

    _maybe_override_llm(llm_provider)

    pi = PipelineInput(
        mode=InputMode.LYRICS_TEXT,
        song_title=song,
        artist=artist,
        raw_lyrics=raw_text,
        output_formats=_parse_formats(output),
        output_file=output_file,
    )
    result = run_and_format(pi)
    if result.error:
        raise typer.Exit(code=1)


@app.command("translate-audio")
def translate_audio(
    audio_file: str = typer.Option(..., "--audio-file", "-a", help="Path to audio file"),
    song: Optional[str] = typer.Option(None, "--song", "-s", help="Song title (optional metadata)"),
    artist: Optional[str] = typer.Option(None, "--artist", help="Artist name (optional metadata)"),
    output: str = typer.Option("console", "--output", "-o", help=_OUTPUT_HELP),
    output_file: Optional[str] = typer.Option(None, "--output-file", "-f", help=_FILE_HELP),
    llm_provider: Optional[str] = typer.Option(None, "--llm", help=_LLM_HELP),
    verbose: bool = typer.Option(False, "--verbose", "-v", help=_VERBOSE_HELP),
) -> None:
    """Transcribe an audio file and translate the resulting lyrics."""
    if verbose:
        configure_level("DEBUG")

    _maybe_override_llm(llm_provider)

    pi = PipelineInput(
        mode=InputMode.AUDIO_FILE,
        song_title=song,
        artist=artist,
        audio_file_path=audio_file,
        output_formats=_parse_formats(output),
        output_file=output_file,
    )
    result = run_and_format(pi)
    if result.error:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _maybe_override_llm(provider_name: str | None) -> None:
    """Mutate settings singleton to use a different LLM provider at runtime."""
    if provider_name:
        settings = get_settings()
        settings.llm.provider = provider_name  # type: ignore[assignment]
        logger.info(f"LLM provider overridden to: {provider_name}")
