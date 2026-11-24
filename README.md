# Math_books

Tools and pipelines for:
1. **STEM-Basketball Vertical Shorts (`9:16`, `1080×1920`, `30 fps`)** — engaging 55–70s Russian educational videos built with **Manim + Gemini TTS + ffmpeg**.
2. **Math Book Digitization** — merging scanned book HTML (`mathedu.ru`) with cropped figures from **MinerU** into clean Markdown.

Latest reviewed test video (archived in `test_videos/`): [two free throws and the complement rule](test_videos/video_free_throws/free_throws.mp4)
(`free_throws`, 69.6 s). [Production and Gemini API checks](docs/free-throws-video.md).

All earlier generated videos are marked as **test artifacts** and archived under [`test_videos/`](test_videos/README.md).
New video generations start from a clean slate under `videos/video_<topic>/`.

## Setup

```bash
uv sync
cp .env.example .env
# Fill in GEMINI_API_KEY (and HF-TOKEN / OPENROUTER_API_KEY if needed)
```

System requirements: `ffmpeg`, `ffprobe`, and `pdflatex` (for Manim `MathTex`).

## CLI Usage

```bash
# List available video topics
uv run math-books list

# Required scientific/pedagogical check; exits 1 while any topic is blocked
uv run math-books review all

# Inspect the existing MoneyBART dossier and its blockers
uv run math-books review moneybart

# Generate TTS audio (reuses only clips with matching provenance and checksum)
uv run math-books tts moneybart

# Remove leading/trailing pauses from trusted clips, preserving internal pauses
uv run math-books tts hothand --trim-edges

# Build a complete video: render silent Manim + concat audio + mux + verify streams
uv run math-books build moneybart

# Verify streams AND correspondence to current scene/script/audio
uv run math-books verify moneybart

# Digitization prototype: convert mathedu HTML + MinerU JSON to Markdown
uv run math-books digitize --pages 13-16

# Select one page without changing the original MinerU page mapping
uv run math-books digitize --pages 14 --out-dir /tmp/page-14
```

## Reliability and migration

**Editorial approval is mandatory before topic production.** See
[the review workflow](docs/scenario-review.md). The gate checks evidence mappings, exact arithmetic,
the learning objective and actual recorded scientific/pedagogical judgments for the current source.
`--init` creates a pending template and refuses to overwrite an existing dossier; an already
initialized topic must use its existing file. It never approves a script.
Neither `--force`, `--skip-render` nor an audio cache hit bypasses review.

- Cache validity includes narration text, voice, model policy, prompt revision and WAV checksum.
  Old WAVs without provenance are regenerated. Merely renaming a file does not approve it.
- New immutable WAVs live under `videos/video_<topic>/audio/clips/`; use the relative paths in
  `manifest.json`, rather than assuming `audio/01_hook.wav`. The actual synthesis model is recorded.
  Unchanged clips can be reused without an API key. A failed generation leaves the previous manifest
  and its referenced audio intact. Old clip versions are retained; no automatic deletion occurs.
- TTS, build and verify take a per-topic lock. A concurrent operation exits with a clear error.
- `--trim-edges` uses a -40 dBFS amplitude threshold and retains 100 ms margins.
  It only trims the ends. Listen to the result; silence detection cannot verify pronunciation,
  repeated takes or scientific accuracy. Do not edit immutable clips in place.
- `build` rejects stale scripts, altered/truncated WAVs and untrusted legacy audio before rendering.
  Run `tts <topic>` to migrate a legacy topic; this needs Gemini quota.
- Scene padding measures renderer time and rejects animation overruns. A silent render's
  `.render.json` binds the scene, shared UI, example data, durations and silent MP4 checksum.
  `--skip-render` requires an exact match: changed audio duration requires a fresh render.
- A final `.build.json` binds source, audio and final MP4 checksums. `verify` rejects missing/stale
  provenance, invalid durations, non-30-fps output, long pauses and silence-detector failures.
  Completely silent clips shorter than 1.2 seconds also fail. Equal total durations alone do not
  certify all visual/narration alignment; inspect the animation as well.
- A candidate MP4 is checked before replacing the previous final output. Old exports without
  `.build.json` are retained, but intentionally do not pass the new full verification.
  For a legacy stream-only diagnostic, use `math_books.video_builder.verify_video(Path(...))`.

MinerU JSON must contain `"page_numbers": [13, 14, 15, 16]` mapping `page_idx` to book pages,
or supply `--source-pages 13-16`. This describes the **original input order**, not the requested
subset. An explicit order such as `--source-pages 14,13` is preserved. Missing pages, scans,
ambiguous HTML pages and invalid crop bounds raise errors instead of silently dropping content.

Scientific assumptions and reviewed examples: [content review](docs/content-review.md).

## Development

```bash
# Lint & format check
uv run ruff check src tests
uv run ruff format --check src tests

# Run unit tests
uv run python -m unittest discover -s tests -v
```

## Project Structure

- `src/math_books/video_ui.py` — Shared `9:16` Manim canvas config, color palette, and UI components (`make_badge`, `make_subtitle`, `make_caption`, `make_basketball`, `make_half_court`, `VerticalShortScene`).
- `src/math_books/tts_engine.py` — Shared Gemini TTS synthesizer with automatic model rotation/fallback and `manifest.json` generation.
- `src/math_books/video_builder.py` — End-to-end build, stdlib WAV assembly, `ffmpeg` muxing, and media/provenance verification.
- `src/math_books/cli.py` — Unified `math-books` CLI entry point.
- `src/math_books/*_scene.py` & `generate_*_tts.py` — Individual STEM-Basketball video scenes and scripts.
- `src/math_books/build_sample_md.py` — Book-to-Markdown + cropped figures pipeline.
- `.agents/skills/stem-basketball-video/SKILL.md` — Production runbook for new videos.
