"""Text manipulation and parsing utilities."""

from __future__ import annotations

import json
import re
from typing import Generator, TypeVar

T = TypeVar("T")


def chunk_lines(lines: list[str], size: int) -> Generator[list[str], None, None]:
    """Yield successive chunks of `size` from a list of lines."""
    for i in range(0, len(lines), size):
        yield lines[i : i + size]


def chunk_list(items: list[T], size: int) -> Generator[list[T], None, None]:
    """Generic chunker."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


def safe_json_parse(text: str) -> object:
    """
    Attempt to parse JSON from an LLM response, stripping common noise like
    markdown code fences or leading/trailing prose.
    """
    # Strip markdown fences
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract a JSON array or object
    array_match = re.search(r"\[.*\]", text, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group())
        except json.JSONDecodeError:
            pass

    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        try:
            return json.loads(obj_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response:\n{text[:300]}")


def clean_lyric_text(text: str) -> str:
    """Basic cleanup for raw lyric text (strip section headers, extra whitespace)."""
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        # Drop common Genius-style section markers: [Verse 1], [Chorus], etc.
        if re.match(r"^\[.+\]$", line):
            continue
        if line:
            lines.append(line)
    return "\n".join(lines)
