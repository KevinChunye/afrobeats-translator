"""
Stage 6: Output formatting.

Supports:
  - console   : rich-formatted table + summary
  - json      : structured JSON file
  - markdown  : human-readable Markdown report
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from ..logger import get_logger
from ..models import PipelineResult

logger = get_logger(__name__)
console = Console()


# ---------------------------------------------------------------------------
# Console (Rich)
# ---------------------------------------------------------------------------


def print_console(result: PipelineResult) -> None:
    """Pretty-print result to stdout using Rich."""

    title = f"[bold magenta]{result.song_title or 'Unknown Song'}[/]"
    if result.artist:
        title += f" [dim]by[/] [bold cyan]{result.artist}[/]"

    console.print()
    console.print(Panel(title, box=box.DOUBLE_EDGE))
    console.print()

    # Line translations table
    table = Table(
        show_header=True,
        header_style="bold yellow",
        box=box.SIMPLE_HEAVY,
        expand=True,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Original", style="white")
    table.add_column("Natural Translation", style="green")
    table.add_column("Slang / Notes", style="cyan")
    table.add_column("Conf.", style="dim", width=6)

    for lt in result.line_translations:
        conf_str = f"{lt.confidence:.0%}"
        conf_style = "green" if lt.confidence >= 0.8 else ("yellow" if lt.confidence >= 0.5 else "red")
        note = lt.slang_explanation or lt.notes or ""
        if lt.ambiguous_phrases:
            note += f" [dim](ambiguous: {', '.join(lt.ambiguous_phrases)})[/dim]"
        table.add_row(
            str(lt.line_number),
            lt.original_line,
            lt.translation_natural or lt.translation_literal,
            note,
            f"[{conf_style}]{conf_str}[/]",
        )

    console.print(table)

    # Song summary
    summary = result.song_summary
    if summary.plain_english_summary:
        console.print()
        console.print(Panel("[bold]Song Summary[/bold]", box=box.ROUNDED))
        if summary.main_theme:
            console.print(f"[bold]Theme:[/bold] {summary.main_theme}")
        if summary.emotional_tone:
            console.print(f"[bold]Tone:[/bold] {summary.emotional_tone}")
        if summary.language_mix:
            console.print(f"[bold]Languages:[/bold] {', '.join(summary.language_mix)}")
        if summary.recurring_slang:
            console.print(f"[bold]Key slang:[/bold] {', '.join(summary.recurring_slang)}")
        console.print()
        console.print(summary.plain_english_summary)

    if result.processing_notes:
        console.print()
        for note in result.processing_notes:
            console.print(f"[dim]ℹ {note}[/dim]")


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def write_json(result: PipelineResult, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
    logger.info(f"JSON output written → {path}")


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def write_markdown(result: PipelineResult, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    title = result.song_title or "Unknown Song"
    artist = result.artist or ""
    lines.append(f"# {title}")
    if artist:
        lines.append(f"**Artist:** {artist}  ")
    lines.append(f"**Source:** {result.raw_lyrics_source}  ")
    lines.append(f"**Mode:** {result.input_mode.value}  ")
    lines.append("")

    # Summary
    summary = result.song_summary
    if summary.plain_english_summary:
        lines.append("## Song Summary")
        if summary.main_theme:
            lines.append(f"**Theme:** {summary.main_theme}  ")
        if summary.emotional_tone:
            lines.append(f"**Tone:** {summary.emotional_tone}  ")
        if summary.language_mix:
            lines.append(f"**Languages:** {', '.join(summary.language_mix)}  ")
        if summary.recurring_slang:
            lines.append(f"**Key slang:** {', '.join(summary.recurring_slang)}  ")
        lines.append("")
        lines.append(summary.plain_english_summary)
        lines.append("")

    # Line-by-line table
    lines.append("## Line-by-Line Translation")
    lines.append("")
    lines.append("| # | Original | Natural Translation | Slang / Notes | Confidence |")
    lines.append("|---|----------|---------------------|---------------|-----------|")

    for lt in result.line_translations:
        original = lt.original_line.replace("|", "\\|")
        natural = (lt.translation_natural or lt.translation_literal).replace("|", "\\|")
        note = (lt.slang_explanation or lt.notes or "").replace("|", "\\|")
        conf = f"{lt.confidence:.0%}"
        lines.append(f"| {lt.line_number} | {original} | {natural} | {note} | {conf} |")

    lines.append("")

    if result.processing_notes:
        lines.append("## Processing Notes")
        for note in result.processing_notes:
            lines.append(f"- {note}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info(f"Markdown report written → {path}")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def format_output(
    result: PipelineResult,
    formats: list[str],
    output_file: str | None = None,
) -> None:
    """Dispatch to one or more output formatters."""
    for fmt in formats:
        if fmt == "console":
            print_console(result)
        elif fmt == "json":
            path = output_file or f"output/{result.song_title or 'result'}.json"
            write_json(result, path)
        elif fmt == "markdown":
            path = output_file or f"output/{result.song_title or 'result'}.md"
            if output_file and not output_file.endswith(".md"):
                path = output_file.rsplit(".", 1)[0] + ".md"
            write_markdown(result, path)
        else:
            logger.warning(f"Unknown output format: {fmt!r}")
