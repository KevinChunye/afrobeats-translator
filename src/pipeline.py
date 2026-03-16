"""
Main pipeline orchestrator.

Ties together all stages for both lyrics-first and audio-first paths.
Each stage is optional/graceful — if a stage fails it logs a warning and
continues with the best available data.
"""

from __future__ import annotations

from .config import get_settings
from .logger import get_logger
from .models import InputMode, LineTranslation, PipelineInput, PipelineResult, RawLyrics
from .providers.llm_provider import LLMProvider, build_llm_provider
from .services.audio_preprocess import preprocess_audio
from .services.explain import generate_song_summary
from .services.formatter import format_output
from .services.lyrics_ingest import ingest_lyrics
from .services.normalize import normalize_lyrics
from .services.transcribe import transcribe_audio, transcript_to_raw_lyrics
from .services.translate import translate_lines
from .utils.files import validate_audio_file
from .utils.text import clean_lyric_text

logger = get_logger(__name__)


def run_pipeline(
    pipeline_input: PipelineInput,
    glossary: dict[str, str] | None = None,
    llm: LLMProvider | None = None,
) -> PipelineResult:
    """
    Execute the full translation pipeline and return a PipelineResult.

    Args:
        pipeline_input: Specifies the input mode and source data.
        glossary:       Optional {term: meaning} dict injected into the
                        normalization prompt for custom slang definitions.
        llm:            Optionally supply a pre-built LLM provider (useful for
                        testing or when reusing a session).
    """
    settings = get_settings()
    provider = llm or build_llm_provider()
    processing_notes: list[str] = []

    result = PipelineResult(
        song_title=pipeline_input.song_title,
        artist=pipeline_input.artist,
        input_mode=pipeline_input.mode,
    )

    # ------------------------------------------------------------------
    # Step 1: Acquire raw lyrics
    # ------------------------------------------------------------------
    raw_lyrics: RawLyrics | None = None

    if pipeline_input.mode in (InputMode.LYRICS_SONG, InputMode.LYRICS_TEXT):
        try:
            raw_lyrics = ingest_lyrics(pipeline_input)
            result.raw_lyrics_source = raw_lyrics.source
            processing_notes.append(f"Lyrics source: {raw_lyrics.source}")
        except Exception as exc:
            logger.error(f"Lyrics ingestion failed: {exc}")
            result.error = str(exc)
            result.processing_notes = processing_notes
            return result

    elif pipeline_input.mode == InputMode.AUDIO_FILE:
        if not pipeline_input.audio_file_path:
            result.error = "audio_file_path must be set for AUDIO_FILE mode"
            return result

        try:
            validate_audio_file(pipeline_input.audio_file_path)
        except (FileNotFoundError, ValueError) as exc:
            result.error = str(exc)
            return result

        # Step 1a: Vocal isolation (optional)
        try:
            processed_audio = preprocess_audio(pipeline_input.audio_file_path)
            if processed_audio != pipeline_input.audio_file_path:
                processing_notes.append("Vocal isolation applied")
            else:
                processing_notes.append("Vocal isolation skipped (using raw audio)")
        except Exception as exc:
            logger.warning(f"Audio preprocessing error: {exc}")
            processed_audio = pipeline_input.audio_file_path
            processing_notes.append(f"Audio preprocessing failed: {exc}")

        # Step 1b: Transcription
        try:
            transcript = transcribe_audio(processed_audio)
            raw_lyrics = transcript_to_raw_lyrics(
                transcript,
                song_title=pipeline_input.song_title,
                artist=pipeline_input.artist,
            )
            result.raw_lyrics_source = "transcription"
            processing_notes.append(f"Transcribed via {settings.transcription.provider}")
        except Exception as exc:
            logger.error(f"Transcription failed: {exc}")
            result.error = str(exc)
            result.processing_notes = processing_notes
            return result

    if raw_lyrics is None:
        result.error = "Could not acquire lyrics from any source"
        result.processing_notes = processing_notes
        return result

    # Clean section headers (e.g. [Chorus]) from lyrics text
    raw_lyrics.raw_text = clean_lyric_text(raw_lyrics.raw_text)
    raw_lyrics.lines = [
        line.strip()
        for line in raw_lyrics.raw_text.splitlines()
        if line.strip()
    ]

    # ------------------------------------------------------------------
    # Step 2: Normalization
    # ------------------------------------------------------------------
    logger.info("Stage: Normalization")
    try:
        normalized = normalize_lyrics(raw_lyrics, llm=provider, glossary=glossary)
    except Exception as exc:
        logger.warning(f"Normalization failed: {exc}. Falling back to raw lines.")
        from .services.normalize import NormalizedLine
        normalized = [
            NormalizedLine(
                original_line=line,
                cleaned_line=line,
                is_pidgin_heavy=False,
                ambiguous_phrases=[],
            )
            for line in raw_lyrics.lines
        ]
        processing_notes.append(f"Normalization skipped: {exc}")

    # ------------------------------------------------------------------
    # Step 3: Translation
    # ------------------------------------------------------------------
    logger.info("Stage: Translation")
    try:
        line_translations = translate_lines(normalized, llm=provider)
    except Exception as exc:
        logger.warning(f"Translation failed: {exc}.")
        line_translations = [
            LineTranslation(
                line_number=i + 1,
                original_line=nl.original_line,
                cleaned_line=nl.cleaned_line,
                notes=f"Translation unavailable: {exc}",
            )
            for i, nl in enumerate(normalized)
        ]
        processing_notes.append(f"Translation skipped: {exc}")

    result.line_translations = line_translations

    # ------------------------------------------------------------------
    # Step 4: Song-level summary
    # ------------------------------------------------------------------
    logger.info("Stage: Song summary")
    try:
        result.song_summary = generate_song_summary(
            song_title=pipeline_input.song_title,
            artist=pipeline_input.artist,
            line_translations=line_translations,
            llm=provider,
        )
    except Exception as exc:
        logger.warning(f"Song summary failed: {exc}")
        processing_notes.append(f"Summary generation skipped: {exc}")

    result.processing_notes = processing_notes
    return result


def run_and_format(
    pipeline_input: PipelineInput,
    glossary: dict[str, str] | None = None,
    llm: LLMProvider | None = None,
) -> PipelineResult:
    """Convenience wrapper: run the pipeline then format output."""
    result = run_pipeline(pipeline_input, glossary=glossary, llm=llm)

    if result.error:
        logger.error(f"Pipeline failed: {result.error}")

    format_output(
        result,
        formats=pipeline_input.output_formats,
        output_file=pipeline_input.output_file,
    )
    return result
