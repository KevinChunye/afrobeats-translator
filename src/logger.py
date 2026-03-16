"""Centralized logging setup using Rich for beautiful console output."""

from __future__ import annotations

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler

console = Console(stderr=True)
_configured = False


def get_logger(name: str = "afrobeats") -> logging.Logger:
    global _configured
    if not _configured:
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[
                RichHandler(
                    console=console,
                    rich_tracebacks=True,
                    markup=True,
                    show_path=False,
                )
            ],
        )
        _configured = True
    return logging.getLogger(name)


def configure_level(level: str) -> None:
    logging.getLogger().setLevel(level.upper())
