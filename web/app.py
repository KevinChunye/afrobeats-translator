"""
FastAPI web server for afrobeats-translator.

Rate limiting: FREE_LIMIT searches per IP per day using the server's API key.
After the limit, users can supply their own Anthropic key to continue.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

# Make sure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.config import LLMConfig
from src.models import InputMode, PipelineInput
from src.pipeline import run_pipeline

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="afrobeats-translator", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

FREE_LIMIT = int(os.getenv("FREE_LIMIT", "3"))

# In-memory rate limiting  {ip: {"count": int, "date": date}}
# Resets daily and on server restart — fine for MVP
_usage: dict[str, dict] = defaultdict(lambda: {"count": 0, "date": date.today()})
_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class TranslateRequest(BaseModel):
    song: Optional[str] = None
    artist: Optional[str] = None
    lyrics: Optional[str] = None       # raw lyrics text (alternative to song lookup)
    user_api_key: Optional[str] = None  # user's own Anthropic key


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/translate")
async def translate(req: TranslateRequest, request: Request):
    ip = request.client.host if request.client else "unknown"

    # ---- Rate limiting -------------------------------------------------------
    uses_remaining = -1  # -1 means "using own key, no limit shown"

    if not req.user_api_key:
        async with _lock:
            usage = _usage[ip]
            if usage["date"] != date.today():
                usage["count"] = 0
                usage["date"] = date.today()

            if usage["count"] >= FREE_LIMIT:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": "You've used all your free translations for today.",
                        "limit_reached": True,
                    },
                )
            usage["count"] += 1
            uses_remaining = max(0, FREE_LIMIT - usage["count"])

    # ---- Build LLM provider --------------------------------------------------
    llm_provider = _build_provider(req.user_api_key)

    # ---- Build pipeline input ------------------------------------------------
    if req.lyrics and req.lyrics.strip():
        pi = PipelineInput(
            mode=InputMode.LYRICS_TEXT,
            song_title=req.song or "Unknown",
            artist=req.artist or "Unknown",
            raw_lyrics=req.lyrics.strip(),
            output_formats=[],
        )
    elif req.song:
        pi = PipelineInput(
            mode=InputMode.LYRICS_SONG,
            song_title=req.song.strip(),
            artist=(req.artist or "").strip(),
            output_formats=[],
        )
    else:
        raise HTTPException(status_code=400, detail="Provide a song name or paste lyrics.")

    # ---- Run pipeline --------------------------------------------------------
    try:
        result = run_pipeline(pi, llm=llm_provider)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if result.error:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "song_title": result.song_title,
        "artist": result.artist,
        "summary": result.song_summary.model_dump(),
        "lines": [lt.model_dump() for lt in result.line_translations],
        "source": result.raw_lyrics_source,
        "uses_remaining": uses_remaining,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_provider(user_api_key: Optional[str]):
    """
    Build an LLM provider. If a user key is supplied, bypass the singleton
    and build a fresh Anthropic client directly — avoids mutating global state.
    """
    if user_api_key and user_api_key.strip():
        try:
            import anthropic as _anthropic
            from src.providers.llm_provider import AnthropicProvider

            provider = AnthropicProvider.__new__(AnthropicProvider)
            provider._cfg = LLMConfig(provider="anthropic")
            provider._client = _anthropic.Anthropic(api_key=user_api_key.strip())
            return provider
        except Exception:
            pass  # fall through to default

    from src.providers.llm_provider import build_llm_provider
    return build_llm_provider()


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
