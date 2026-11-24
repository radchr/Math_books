# Math_books — STEM-Basketball & Book Digitization Project

## Overview
This workspace contains tools and pipelines for:
1. **STEM-Basketball Short Videos (9:16 vertical, 1080×1920):** Engaging 55–70s TikTok/Shorts-style educational videos in Russian for a 12-year-old boy who loves basketball, connecting NBA/court phenomena and classic math books (Ahrens 1924, Perelman 1925) to geometry, algebra, probability, and statistics.
2. **Math Book Digitization:** Scripts for downloading scanned pages from `mathedu.ru`, cropping illustrations via Hugging Face `opendatalab/MinerU`, and assembling clean Markdown (`data/sample_md/`).

## Tech Stack & Environment
- **Package Manager:** `uv` (Python `>=3.13`, `.venv`)
- **Video, Audio & Math Animation:** `manim==0.22.1`, `ffmpeg`/`ffprobe`, `latex`/`pdflatex`, stdlib `wave` + `numpy`, `pillow`
- **Local Voiceover QA & Russian NLP:** `faster-whisper` (`base` int8 CPU), `pymorphy3`, `num2words`, `snowballstemmer`
- **TTS & AI APIs (`.env` — never commit or print secrets):**
  - `GEMINI_API_KEY` — Gemini TTS (`gemini-3.8-flash-tts`, `gemini-2.5-flash-preview-tts`, `gemini-3.8-flash-lite-tts`)
  - `HF-TOKEN` — Hugging Face Spaces (`gradio_client` for `opendatalab/MinerU`; note hyphenated env var name)
  - `OPENROUTER_API_KEY` — OpenRouter free vision/text models

## Project Structure
- `src/math_books/`
  - `cli.py` — Unified `math-books` CLI (`list`, `review`, `tts`, `verify-audio`, `build`, `verify`, `digitize`)
  - `content_review.py` — Offline scientific & pedagogical review gate validating `content_reviews/<topic>.json` dossiers and exact math checks
  - `voiceover_qa.py` & `spoken_text.py` — Local `faster-whisper` ASR verification gate, Russian number/morphology normalizer, and version-bound QA receipts (`audio/qa/`)
  - `lesson_math.py` — Exact mathematical example helpers shared between scenes, tests, and review checks
  - `video_ui.py` — Shared `9:16` Manim config, theme constants, `VerticalShortScene` (`run_segment`, `_pad`, `word_timestamp`, `check_frame_bounds`), and reusable UI helpers (`make_badge`, `make_subtitle`, `make_caption`, `make_basketball`, `make_half_court`, `make_scoreboard`, `make_stat_card`)
  - `tts_engine.py` — Shared Gemini TTS helper (`synthesize_gemini_tts`, `generate_topic_tts`) with automatic model rotation, immutable clips (`audio/clips/`), edge trimming, local ASR verification & `manifest.json` generation
  - `video_builder.py` — Automated silent Manim render, lossless stdlib `wave` concatenation, `ffmpeg` muxing (`-movflags +faststart`), `ffprobe` + provenance verification, and preview frame extraction
  - `generate_tts.py` / `basketball_triangles_scene.py` — Triangles in basketball video (`basketball`)
  - `generate_ahrens_tts.py` / `ahrens_basketball_scene.py` — Ahrens 1924 "Race to 100" adapted to 21-point basketball duel (`ahrens`)
  - `generate_simpson_tts.py` / `simpson_basketball_scene.py` — Simpson's Paradox in basketball shooting stats (`simpson`)
  - `generate_moneybart_tts.py` / `moneybart_scene.py` — MoneyBART expected value (`35% × 3 = 1.05 > 50% × 2 = 1.00`, `moneybart`)
  - `generate_hothand_tts.py` / `hothand_scene.py` — Hot Hand selection bias (`5/12` vs `1/2`, Miller & Sanjurjo 2018, `hothand`)
  - `generate_free_throws_tts.py` / `free_throws_scene.py` — Two free throws & complement rule (`1 - 0.3² = 91%`, `free_throws`)
  - `build_sample_md.py` — Book-to-Markdown + cropped figures pipeline (`--pages` and `--source-pages` CLI support)
- `content_reviews/<topic>.json` — Version-bound scientific and pedagogical review dossiers (archived revisions in `content_reviews/history/`)
- `tests/` — Unit and regression suites (`test_math_books.py`, `test_content_review.py`, `test_reliability.py`, `test_spoken_text.py`, `test_voiceover_qa.py`, `test_voiceover_pipeline.py`, `test_free_throws.py`, `test_lesson_math.py`)
- `videos/video_<topic>/` — Clean workspace for all newly generated production `.mp4` videos and `audio/` manifests
- `test_videos/video_<topic>/` — Archived test videos and audio from earlier iterations (`video_basketball`, `video_ahrens`, `video_simpson`, `video_moneybart`, `video_hothand`, `video_free_throws`)
- `.agents/skills/stem-basketball-video/SKILL.md` — Detailed runbook for creating new STEM-Basketball videos

## Critical Project Conventions
1. **Always use `uv run`** when executing Python or `manim` commands.
2. **Manim + Audio Sync:** Do NOT use `self.add_sound()` inside `Scene` (Manim caching drops audio on subsequent scenes). Always render a silent `.mp4` and mux the `wave`-concatenated `.wav` track via `ffmpeg`. Use `self.run_segment(segment_fn, duration)` and `self._pad(duration)` (which measures authoritative `self.renderer.time` and runs `self.check_frame_bounds()`), use `self.word_timestamp(scene_id, target_word, fallback=..., after_s=...)` for intra-scene word-level answer reveals from `audio/qa/*.json`, and fade out scenes with `FadeOut(Group(*self.mobjects), run_time=0.4)`.
3. **LaTeX & Cyrillic:** Never pass Cyrillic text inside `MathTex()` (standard `latex` fails on Cyrillic). Use `Text(..., font="DejaVu Sans")` for Russian labels and `MathTex()` strictly for pure math/Latin/Greek formulas.
4. **Vertical Frame Safety:** For `1080×1920` (`frame_width=9.0`), always constrain text width (`scale_to_fit_width(7.6)` or `7.8`), rely on automatic `self.check_frame_bounds()` (`|x| <= 4.35`, `y in [-6.15, +7.45]`), and visually inspect extracted frames with `read_file`.
5. **TTS Quality Control & Local ASR Gate:** Every synthesized or cached clip is automatically checked against the Russian script via local `faster-whisper` (`voiceover_qa.py`), rejecting leaked English prompts, repeated takes, and altered numbers/negations/math terms. Run `uv run math-books verify-audio <topic>` to inspect or `--refresh` ASR receipts (`audio/qa/`). Also listen to or inspect WAVs from `manifest.json` (stored immutably under `videos/video_<topic>/audio/clips/`) because ASR cannot certify Russian word stress. Use `math-books tts <topic> --trim-edges` for leading/trailing silence. Never modify immutable clips in place.
6. **Reliable Builds:** `build` requires trusted audio provenance and passing ASR QA; `verify` also requires the final `.build.json`. Missing sidecars are failures, not evidence that an old export is current. `--skip-render` requires unchanged scene/example data, audio timing, and `.render.json` checksums. See `docs/content-review.md` for scientific assumptions and known artifact limitations.
7. **Mandatory Script Review:** Before any topic TTS/render, run `uv run math-books review <topic>` and require `ok: true`. See `docs/scenario-review.md` and `content_reviews/<topic>.json`. Both scientific and pedagogical judgments must refer to the current dossier hash. `--force` and cached audio do not bypass this. Never fabricate approval or copy old verdicts onto changed content. Record AI reviewers as AI. The gate checks recorded judgments and exact calculations, not scientific truth automatically.
