# 🎵 afrobeats-translator

> Understand every lyric. Feel every word.

A modular AI pipeline that translates **Afrobeats and Amapiano** lyrics from Nigerian English / Nigerian Pidgin / mixed slang into plain English — with **line-by-line translation**, **slang explanation**, and **cultural context**.

Built with Claude + OpenAI. Works with lyrics text, raw input, or audio files.

---

## Demo

### Wizkid — Essence
```
  #   Original                                   Natural Translation                        Slang / Notes
  1   You don cast your spell on me, can't        You've enchanted me, I can't explain it
      explain it
  3   Baby girl, you sweet like agbalumo          Baby girl, you're as sweet as agbalumo    Agbalumo = African star apple 🍊
  4   You dey make my body vibrate, e dey do me   You make my body vibrate, it moves me     'dey' = continuous tense in Pidgin
  5   Come make we fall in love, e go sweet       Let's fall in love, it'll be wonderful    'e go sweet' = it will be great
  10  E be like say na God arrange am             It feels like it was divinely arranged    Full Pidgin phrase breakdown ↓
```
**Song summary:** Wizkid expresses overwhelming attraction — her waist, eyes, and sweetness (compared to agbalumo fruit) have him spellbound. He frames their meeting as divinely arranged. Mix: English + Nigerian Pidgin + Yoruba.

---

### 1da Banton — No Wahala
```
  #   Original                                        Natural Translation
  1   She no get wahala, she no get drama             She has no problems, no drama
  6   This girl dey make sense, she no dey cause      This girl is sensible, she doesn't cause problems
      palava
  7   She cook for me, she pray for me, she sabi      She cooks, prays for me, and gets the situation
      the saga
  11  Wahala don finish since I find her              My troubles ended when I found her
  14  No cap, this love go last till manana           Honestly, this love will last forever         90% confidence
```
**Song summary:** A man celebrates a loving, drama-free relationship. He appreciates her genuine support and commits to her — even planning to propose. Mix: English + Nigerian Pidgin.

---

## What It Does

| Stage | Description |
|---|---|
| **Lyric ingestion** | Fetch by song title + artist, or paste raw text |
| **Audio preprocessing** | Optional vocal isolation (Demucs / stub) |
| **Transcription** | OpenAI Whisper cloud or stub |
| **Normalization** | LLM rewrites Pidgin-heavy lines into clean intermediate form |
| **Translation** | Line-by-line: literal + natural English |
| **Explanation** | Slang glossary + cultural notes per line |
| **Song summary** | Theme, tone, language mix, plain-English overview |
| **Output** | Console (Rich), JSON file, Markdown report |

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/afrobeats-translator.git
cd afrobeats-translator

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set your API key

```bash
# Option A — export in terminal (one session)
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export OPENAI_API_KEY="sk-..."

# Option B — save to .env file (persists)
cp .env.example .env
# then edit .env and fill in your key
```

> The pipeline **runs without any API keys** using mock lyrics and stub providers — useful for testing the architecture.

### 3. Run

```bash
# Translate a song (uses mock lyrics DB)
python main.py translate-song --song "Essence" --artist "Wizkid"

# Translate a lyrics text file
python main.py translate-lyrics --input-file data/sample_lyrics.txt

# Translate inline lyrics
python main.py translate-lyrics \
  --lyrics "Soro soke werey\nOya burst am tonight\nWahala dey but e go be alright"

# Translate from an audio file (requires OPENAI_API_KEY for Whisper)
python main.py translate-audio --audio-file song.mp3 --song "My Song"

# Save as JSON + Markdown report
python main.py translate-song --song "No Wahala" --artist "1da Banton" \
  --output "console,json,markdown" --output-file output/no_wahala.json

# Force a specific LLM provider
python main.py translate-song --song "Essence" --artist "Wizkid" --llm openai

# Debug mode
python main.py translate-song --song "Essence" --artist "Wizkid" --verbose
```

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Recommended | Default LLM (normalization, translation, summary) |
| `OPENAI_API_KEY` | Optional | Alternative LLM + Whisper audio transcription |
| `DEEPSEEK_API_KEY` | Optional | Alternative budget LLM |
| `ELEVENLABS_API_KEY` | Optional | Future vocal isolation (stub for now) |
| `GENIUS_ACCESS_TOKEN` | Optional | Real lyrics fetching via Genius API |

---

## Output Schema

Each lyric line returns:

```json
{
  "line_number": 3,
  "original_line": "Baby girl, you sweet like agbalumo",
  "cleaned_line": "Baby girl, you are as sweet as agbalumo",
  "translation_literal": "Baby girl, you are sweet like agbalumo",
  "translation_natural": "Baby girl, you're as sweet as agbalumo fruit",
  "slang_explanation": "Agbalumo is the African star apple, a beloved Nigerian fruit known for its sweet-sour taste.",
  "confidence": 0.98,
  "notes": "Comparing someone to agbalumo signals irresistible sweetness — a culturally loaded compliment.",
  "is_pidgin_heavy": false,
  "ambiguous_phrases": []
}
```

Plus a song-level summary:

```json
{
  "main_theme": "Deep romantic admiration and a sense of divine destiny",
  "emotional_tone": "Romantic, sensual, joyful",
  "recurring_slang": ["no cap", "agbalumo", "e dey do me", "wey", "dey"],
  "plain_english_summary": "Wizkid expresses overwhelming attraction...",
  "language_mix": ["English", "Nigerian Pidgin", "Yoruba"]
}
```

---

## Project Structure

```
afrobeats-translator/
  main.py                         CLI entry point
  requirements.txt
  .env.example
  data/
    sample_lyrics.txt             Sample lyrics for offline testing
  src/
    config.py                     pydantic-settings: LLM / audio / transcription
    models.py                     Pydantic data contracts
    logger.py                     Rich-based structured logging
    pipeline.py                   Main orchestrator
    cli.py                        Typer CLI (3 commands)
    providers/
      llm_provider.py             Anthropic / OpenAI / DeepSeek + fallback factory
      lyrics_provider.py          Mock / Genius / Manual + factory
      transcription_provider.py   OpenAI Whisper / Google Speech (stub) / Stub
      audio_isolation_provider.py Demucs / ElevenLabs (stub) / Stub
    services/
      lyrics_ingest.py            Stage 1 — lyrics acquisition
      audio_preprocess.py         Stage 1 — vocal isolation
      transcribe.py               Stage 2 — audio → text
      normalize.py                Stage 3 — Nigerian lyric intelligence
      translate.py                Stage 4 — line-by-line translation
      explain.py                  Stage 5 — song summary
      formatter.py                Stage 6 — console / JSON / markdown output
    utils/
      text.py                     JSON parsing, chunking, lyric cleanup
      files.py                    Audio validation, path helpers
  tests/
    test_pipeline.py
    test_normalize.py
    test_translate.py
```

---

## Running Tests

Tests use fake LLM providers — no API keys needed:

```bash
python -m pytest tests/ -v
# 24 passed
```

---

## Design Principles

**Graceful degradation** — every stage has a fallback. Missing key → stub. LLM timeout → `confidence=0.0` placeholder. The pipeline always produces output.

**Two-step LLM prompting** — normalization (pidgin cleanup + slang detection) is separate from translation. Each prompt is focused, and you can swap the normalization model independently.

**Chunked calls** — all LLM requests batch lines (default 15–20) to handle full albums within token limits.

**Honest stubs** — `ElevenLabsIsolationProvider` and `GoogleSpeechProvider` are real classes with clear `TODO` docstrings, not silent no-ops.

---

## Roadmap

- [ ] **Real lyrics API** — Genius / Musixmatch integration + caching
- [ ] **Custom slang glossary** — load from YAML, inject into normalization prompt
- [ ] **Local Whisper** — fully offline transcription via `openai-whisper`
- [ ] **Demucs vocal isolation** — stem separation for cleaner transcription
- [ ] **Web UI** — FastAPI + simple frontend
- [ ] **Streaming output** — stream LLM tokens to console
- [ ] **Fine-tuned model** — train on a Nigerian slang glossary dataset
- [ ] **Spotify / YouTube** — look up and fetch audio by URL

---

## Tech Stack

- **Python 3.9+**
- **Pydantic v2** — data models and settings
- **Typer** — CLI
- **Rich** — terminal formatting
- **Anthropic / OpenAI / DeepSeek** — LLM providers
- **OpenAI Whisper** — audio transcription

---

## Contributing

PRs welcome. To add a new song to the mock lyrics database, edit `src/providers/lyrics_provider.py` and add an entry to `_MOCK_LYRICS`.

To add a new language or dialect, the key file is `src/services/normalize.py` — update the `SYSTEM_PROMPT` with the relevant linguistic context.
