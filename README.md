# afrobeats-translator

A modular pipeline that helps listeners understand Afrobeats and Amapiano songs
by translating Nigerian English / Nigerian Pidgin / slang-heavy lyrics into
plain English with cultural explanation.

---

## Features

| Stage | What it does |
|---|---|
| **Lyric ingestion** | Fetches lyrics by song title + artist, or accepts raw text |
| **Audio preprocessing** | Optional vocal isolation (Demucs / stub) |
| **Transcription** | OpenAI Whisper cloud or stub |
| **Normalization** | LLM rewrites noisy / Pidgin-heavy lines into cleaned intermediate form |
| **Translation** | Line-by-line literal + natural English translation |
| **Explanation** | Song-level summary: theme, tone, slang glossary |
| **Output** | Console (Rich), JSON file, Markdown report |

---

## Quick Start

### 1. Install dependencies

```bash
cd afrobeats-translator
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
cp .env.example .env
# Edit .env with your API keys — at minimum set ANTHROPIC_API_KEY or OPENAI_API_KEY
```

The pipeline **works without any API keys** by falling back to mock lyrics and
stub providers. You'll get placeholder translations, but it proves the pipeline
runs end-to-end.

### 3. Run

```bash
# Translate a song (fetches mock lyrics if Genius not configured)
python main.py translate-song --song "Essence" --artist "Wizkid"

# Translate a local lyrics file
python main.py translate-lyrics --input-file data/sample_lyrics.txt --song "My Song"

# Translate and save as JSON + Markdown
python main.py translate-song --song "Fall" --artist "Davido" \
  --output "console,json,markdown" --output-file output/fall.json

# Translate from audio file (requires OPENAI_API_KEY for Whisper)
python main.py translate-audio --audio-file data/song.mp3 --song "My Song"

# Switch LLM provider at runtime
python main.py translate-song --song "Essence" --artist "Wizkid" --llm openai

# Verbose debug output
python main.py translate-song --song "Essence" --artist "Wizkid" --verbose
```

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Recommended | Default LLM (normalization, translation, summary) |
| `OPENAI_API_KEY` | Optional | Alternative LLM + Whisper transcription |
| `DEEPSEEK_API_KEY` | Optional | Alternative LLM |
| `ELEVENLABS_API_KEY` | Optional | Future vocal isolation (stub for now) |
| `GOOGLE_API_KEY` | Optional | Google Speech transcription (stub for now) |
| `GENIUS_ACCESS_TOKEN` | Optional | Real lyrics fetching via Genius |

---

## Project Structure

```
afrobeats-translator/
  main.py                         Entry point
  requirements.txt
  .env.example
  src/
    __init__.py
    config.py                     Settings (pydantic-settings)
    models.py                     Pydantic data models
    logger.py                     Rich-based logging
    pipeline.py                   Main orchestrator
    cli.py                        Typer CLI
    providers/
      llm_provider.py             Anthropic / OpenAI / DeepSeek
      lyrics_provider.py          Mock / Genius / Manual
      transcription_provider.py   Whisper / Google / Stub
      audio_isolation_provider.py Demucs / ElevenLabs / Stub
    services/
      lyrics_ingest.py            Stage 1 (lyrics path)
      audio_preprocess.py         Stage 1 (audio path — isolation)
      transcribe.py               Stage 2 (audio path — transcription)
      normalize.py                Stage 3 — Nigerian lyric intelligence
      translate.py                Stage 4 — line translation
      explain.py                  Stage 5 — song summary
      formatter.py                Stage 6 — output formatting
    utils/
      text.py                     JSON parsing, chunking, text cleanup
      files.py                    File validation helpers
  tests/
    test_pipeline.py
    test_normalize.py
    test_translate.py
  data/
    sample_lyrics.txt             Sample Afrobeats lyrics for testing
```

---

## Architecture & Design Choices

### Modular provider pattern
Every external dependency (LLM, lyrics, transcription, audio) has a minimal
Protocol interface with multiple implementations. Swap providers by changing
one line in `config.py` or passing `--llm` on the CLI.

### Graceful degradation
No stage raises an unhandled exception. If a provider is unavailable (missing
key, network error), the pipeline logs a warning and falls back to a stub.
This means `python main.py translate-song --song X --artist Y` always produces
*some* output, even with zero API keys.

### LLM prompt engineering
- **Normalization prompt**: asks for cleaned lines, pidgin-heavy flags, and
  ambiguous phrases — not full translation. Keeps stages independent.
- **Translation prompt**: explicitly instructs the model to lower confidence
  on uncertain lines rather than hallucinating, and to distinguish literal
  vs. natural translations.
- **Summary prompt**: holistic analysis after all lines are translated, so
  the model has full context.

### Chunked LLM calls
Lines are sent in configurable batches (default 15–20) so the pipeline handles
songs of any length within token limits.

### Pydantic everywhere
All inter-stage data uses Pydantic models, making the pipeline easy to test,
serialize, and extend.

---

## Running Tests

```bash
pytest tests/ -v
# With coverage
pytest tests/ -v --cov=src --cov-report=term-missing
```

Tests use fake LLM providers and run completely offline.

---

## Future Improvements

- [ ] **Genius / Musixmatch integration** — add real lyrics API with caching
- [ ] **Custom slang glossary** — load from YAML/JSON, inject into normalization prompt
- [ ] **Local Whisper** — `pip install openai-whisper` for fully offline transcription
- [ ] **Demucs vocal isolation** — `pip install demucs` for stem separation
- [ ] **Language detection** — auto-detect Yoruba, Igbo, Amapiano slang
- [ ] **Web UI** — FastAPI + simple frontend
- [ ] **Streaming output** — stream LLM tokens to console for faster perceived response
- [ ] **Fine-tuned model** — train/fine-tune on a Nigerian slang glossary dataset
- [ ] **Spotify / YouTube integration** — look up song by URL and auto-fetch audio
