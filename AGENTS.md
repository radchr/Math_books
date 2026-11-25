# Math_books — STEM Short Videos & Book Digitization Project

## Overview
This workspace contains tools and pipelines for:
1. **STEM & STEM-Basketball Short Videos (9:16 vertical, 1080×1920):** Engaging TikTok/Shorts-style educational videos (`uk`/`ru`/`en`) connecting classic science/math books (Ahrens 1924, Perelman 1925, etc.) and real-world/NBA phenomena to mathematics, physics, chemistry, biology, probability, and statistics. Supports both **voiceover (TTS + ASR QA)** (55–70s) and **`music_only`** (reusable music bed + on-screen captions/diagrams, 20–45s). The 7 legacy Russian basketball Python scenes remain intact.
2. **Math Book Digitization:** Local prototype merging previously downloaded `mathedu.ru` HTML/scans and MinerU JSON, cropping illustrations, and assembling Markdown (`data/sample_md/`). Acquisition/API integrations are not implemented by `digitize`.

## Tech Stack & Environment
- **Package Manager:** `uv` (Python `>=3.13`, `.venv`)
- **Video, Audio & Math Animation:** `manim==0.22.1`, `sympy>=1.14.0`, `ffmpeg`/`ffprobe`, `latex`/`pdflatex`, stdlib `wave` + `numpy`, `pillow`
- **Local Voiceover QA & Multilingual NLP:** `faster-whisper` (`base` int8 CPU for `ru`/`en`, `small` default for `uk`), `pymorphy3`, `num2words`, `snowballstemmer`, plus non-mutating PCM16 acoustic screening (`audio_quality.py`)
- **TTS, Music & AI APIs (`.env` — never commit or print secrets):**
  - `GEMINI_API_KEY` — Primary default TTS for all languages (`uk`, `ru`, `en`) via Gemini TTS (`gemini-3.8-flash-tts`, `gemini-2.5-flash-preview-tts`, `gemini-3.8-flash-lite-tts`), sent via `x-goog-api-key` header (never in URL query strings) with secret redaction on surfaced errors. Also used by optional `lyria` music generation (`lyria-3-clip-preview`).
  - Ukrainian fallback TTS chain (used automatically for `--lang uk` only when Gemini is unavailable, or explicitly via `--lang uk --provider uk`, `voice_profiles.toml`): `StyleTTS2` (`microgravity/styletts2-ukrainian`) → optional local `Piper` (`uk_UA-oleksa-high`, requires external `piper` package & local ONNX models) → `Edge TTS` (`uk-UA-OstapNeural`), with batch voice pinning and 24 kHz mono PCM WAV normalization
  - Reusable music bank (`assets/music/`): local procedural synthesis (`procedural`), optional AI backends (`lyria`, HuggingFace Spaces `musicgen`/`ace_step`), and CC0/royalty-free track import via `ffmpeg` (`math-books music`).
  - Historical acquisition experiments used `HF-TOKEN` / `OPENROUTER_API_KEY`; the current local `digitize` command does not consume these credentials.
- **Quality Gate & CI:** `Justfile` (`just fix`, `just check`, `just test`, `just ci`), `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `ruff`, `ty` (Astral type checker), `unittest` + `hypothesis` property-based tests.

## Project Structure
- `src/math_books/`
  - `cli.py` — Unified `math-books` CLI (`list`, `review`, `tts`, `verify-audio`, `build`, `verify`, `bank`, `music`, `digitize`)
  - `topics.py`, `media_io.py`, `pipeline_errors.py` — Shared topic metadata, low-level WAV/locking/atomic JSON I/O and exception identities without orchestration cycles
  - `content_bank.py` — Git-backed scenario bank (`content/bank/*.json`) with rebuildable SQLite search index (`.cache/bank.sqlite`) and `math-books bank` (`list`, `show`, `search`, `promote`, `reindex`)
  - `content_review.py`, `sympy_checks.py` — Offline scientific & pedagogical review gate validating `content_reviews/<topic>.json` (and `<lang>/<topic>.json`) dossiers, extensible `CHECK_REGISTRY` exact math checks (including safe AST-allowlisted SymPy checkers `sympy_identity`, `sympy_solve`, `sympy_formula_eval` with explicit domain assumptions), and flexible `audience_age` (int or `{min, max}`). Mandatory for both `voiceover` and `music_only` lessons.
  - `voiceover_qa.py`, `spoken_text.py`, `multilingual_numbers.py`, `audio_quality.py` — Local `faster-whisper` ASR verification gate, `ru`/`uk`/`en` number/protected-word normalizers, PCM16 acoustic screening, and version-bound QA receipts (`audio/qa/`)
  - `languages.py`, `lessons.py`, `cue_timeline.py`, `localized_lesson_scene.py` — Declarative three-language (`uk`/`ru`/`en`) lessons (`content/lessons/*.json`), supporting `audio_mode: "voiceover" | "music_only"`, canonical word-cue / timed-cue timeline resolution, and shared `LocalizedLessonScene` renderer
  - `visual_blocks/` — Modular reusable 9:16 visual blocks (`text_card`, `hook_choice`, `compare_bars`, `step_chain`, `challenge_card`, `image_stage`, plus `packs/basketball/{half_court_diagram,scoreboard_duel}`), named themes (`neutral_dark`, `science_lab`, `basketball_dark`), and 3-language UI strings (`ui_strings.json`)
  - `music_tracks.py` — Reusable music bank (`assets/music/manifest.json` + WAVs), `math-books music` (`list`, `generate`, `import`), and `render_music_bed` for `music_only` builds
  - `lesson_math.py` — Exact mathematical example helpers shared between scenes, tests, and review checks
  - `video_ui.py` — Shared `9:16` Manim config, theme constants, `VerticalShortScene` (`run_segment`, `_pad`, `word_timestamp`, `check_frame_bounds`), programmatic layout QA (`check_mobjects_frame_bounds`, `find_mobject_overlaps`, `require_no_mobject_overlaps`), and reusable UI helpers (`make_badge`, `make_subtitle`, `make_caption`, `make_basketball`, `make_half_court`, `make_scoreboard`, `make_stat_card`)
  - `tts_engine.py` — Shared TTS helper (`synthesize_gemini_tts`, `generate_topic_tts`) with Gemini model rotation, `--provider uk` multi-provider Ukrainian fallback, immutable clips (`audio/clips/`), edge trimming, local ASR verification & `manifest.json` generation
  - `uk_tts_providers.py` & `voice_profiles.toml` — Ukrainian TTS fallback chain (`StyleTTS2` → `Piper` → `Edge TTS`), batch voice pinning, and 24 kHz mono PCM WAV normalization
  - `video_builder.py` — Automated silent Manim render (full `1080×1920` or fast `540×960` `--draft`), lossless stdlib `wave` concatenation (or `music_only` music bed rendering), `ffmpeg` muxing (`-movflags +faststart`), `ffprobe` + provenance verification, and multi-point preview keyframe extraction (`start`, post-cue, `final`)
  - `generate_tts.py` / `basketball_triangles_scene.py` — Triangles in basketball video (`basketball`)
  - `generate_ahrens_tts.py` / `ahrens_basketball_scene.py` — Ahrens 1924 "Race to 100" adapted to 21-point basketball duel (`ahrens`)
  - `generate_simpson_tts.py` / `simpson_basketball_scene.py` — Simpson's Paradox in basketball shooting stats (`simpson`)
  - `generate_moneybart_tts.py` / `moneybart_scene.py` — MoneyBART expected value (`35% × 3 = 1.05 > 50% × 2 = 1.00`, `moneybart`)
  - `generate_hothand_tts.py` / `hothand_scene.py` — Hot Hand selection bias (`5/12` vs `1/2`, Miller & Sanjurjo 2018, `hothand`)
  - `generate_free_throws_tts.py` / `free_throws_scene.py` — Two free throws & complement rule (`1 - 0.3² = 91%`, `free_throws`)
  - `generate_buzzer_tts.py` / `buzzer_scene.py` — Direct three-point shot versus an independent three-step chain (`30% > 24.5%`, `buzzer`)
  - `build_sample_md.py` — Book-to-Markdown + cropped figures pipeline (`--pages` and `--source-pages` CLI support)
- `content/bank/<id>.json` — Version-controlled scenario/idea bank (promoted to `content/lessons/<topic>.json` via `math-books bank promote`)
- `content/lessons/<topic>.json` — Declarative three-language (`uk`/`ru`/`en`) lessons (`voiceover` or `music_only`) using `visual_blocks`
- `assets/music/` & `assets/diagrams/` — Reusable CC0/licensed music tracks (`manifest.json` + `.wav`) and SVG/PNG diagrams for `image_stage`
- `content_reviews/<topic>.json` (and `content_reviews/<lang>/<topic>.json` for new multilingual lessons) — Version-bound scientific and pedagogical review dossiers (archived revisions in `content_reviews/history/`, non-active drafts in `content_reviews/proposals/`)
- `tests/` — Unit, regression, layout-stress, and `hypothesis` property-based suites covering CLI, editorial gates + SymPy symbolic checkers (`test_sympy_checks.py`), scenario bank, visual blocks & overlap/bounds stress (`test_visual_layout_stress.py`), `music_only` + music bank, multilingual ASR/acoustic QA, cue timelines, secret redaction, read-only status, atomic I/O, and scene math models
- `videos/video_<topic>/` — Clean workspace for all newly generated production `.mp4` videos and `audio/` manifests
- `test_videos/video_<topic>/` — Archived test videos and audio from earlier iterations (`video_basketball`, `video_ahrens`, `video_simpson`, `video_moneybart`, `video_hothand`, `video_free_throws`)
- `.agents/skills/` — Project-specific agent skills:
  - `stem-basketball-video/SKILL.md` — End-to-end production runbook for creating new 9:16 STEM & STEM-Basketball videos (`voiceover` or `music_only`)
  - `feynman-manim-composer/SKILL.md` — Feynman/Bruner dual-column storyboard composer (Voiceover/Captions ⟷ Manim 9:16 + `visual_blocks`) before coding
  - `anti-slop-review/SKILL.md` — Scientific and pedagogical anti-slop audit protocol before recording `content_reviews/<lang>/<topic>.json` approval

## Critical Project Conventions

### Future multilingual & general STEM lessons

New declarative lessons start in `content/bank/<id>.json` (promoted via `math-books bank promote`)
and compile from `content/lessons/<topic>.json` with complete `uk/ru/en` translations,
reusable `visual_blocks`, and CLI `--lang`. See `docs/three-language-videos.md`.
New media lives in `videos/video_<topic>/<lang>/`; reviews in `content_reviews/<lang>/<topic>.json`.
Lessons may use `audio_mode: "voiceover"` (default, TTS + ASR QA) or `audio_mode: "music_only"`
(music bed from `assets/music/` + on-screen captions/diagrams and timed `cues`).
**`music_only` skips TTS/ASR, but NEVER skips `content_review.py`, bank storage, or build provenance checks.**
Never translate or regenerate the seven legacy topics unless explicitly requested.
Future QA is language-aware; the legacy Python scenes remain Russian. Do not infer
speech language from provider alone or reuse approval between languages.

1. **Always use `uv run`** when executing Python or `manim` commands.
2. **Manim + Audio Sync:** Do NOT use `self.add_sound()` inside `Scene` (Manim caching drops audio on subsequent scenes). Always render a silent `.mp4` and mux the `wave`-concatenated `.wav` track via `ffmpeg`. Use `self.run_segment(segment_fn, duration)` and `self._pad(duration)` (which measures authoritative `self.renderer.time` and runs `self.check_frame_bounds()`), use `self.word_timestamp(scene_id, target_word, fallback=..., after_s=...)` in legacy scenes (consumes the verified `timing_snapshot` with exact Unicode matching) or declared `cues` (`cue_timeline.py`) in declarative lessons, and fade out scenes with `FadeOut(Group(*self.mobjects), run_time=0.4)`.
3. **LaTeX & Cyrillic:** Never pass Cyrillic text inside `MathTex()` (standard `latex` fails on Cyrillic). Use `Text(..., font="DejaVu Sans")` for Russian/Ukrainian labels and `MathTex()` strictly for pure math/Latin/Greek formulas.
4. **Vertical Frame & Overlap Safety:** For `1080×1920` (`frame_width=9.0`), always constrain text width (`scale_to_fit_width(7.6)` or `7.8`), rely on automatic `self.check_frame_bounds()` (`|x| <= 4.35`, `y in [-6.15, +7.45]`) and `require_no_mobject_overlaps()` (in `LocalizedLessonScene`), and visually inspect multi-point extracted preview frames (`start`, post-cue, `final`) with `read_file`.
5. **TTS Quality Control & Local ASR Gate:** Every synthesized or cached clip is automatically checked against the script via local `faster-whisper` (`voiceover_qa.py`, language-aware with per-language protected vocabularies and acoustic screening for new lessons), rejecting leaked prompts, repeated takes, and altered numbers/negations/units/math terms (`needs_review` clips are retained in `audio/review_required/` without blind paid retries). Run `uv run math-books verify-audio <topic>` to inspect or `--refresh` ASR receipts (`audio/qa/`; `music_only` lessons validate their music track without creating `audio/`). Also listen to or inspect WAVs from `manifest.json` (stored immutably under `videos/video_<topic>/audio/clips/`) because ASR cannot certify word stress. Use `math-books tts <topic> --trim-edges` for leading/trailing silence. Never modify immutable clips in place.
6. **Reliable Builds & Read-Only Inventory:** `math-books list` is strictly read-only (never hashes media, runs ASR/ffmpeg, or creates locks) and reports `unverified` or `busy` rather than `verified`. `build` requires trusted audio provenance and passing ASR QA; `verify` also requires the final `.build.json`. Missing sidecars are failures, not evidence that an old export is current. Use `math-books build <topic> --lang <lang> --draft` for fast `540×960` layout/preview checks (`<topic>_draft.mp4` + `preview_frames_draft/`, never overwriting production `.mp4`/`.build.json`). `--skip-render` requires unchanged scene/example data, audio timing, and `.render.json` checksums. See `docs/content-review.md` and `docs/review-hardening.md` for scientific assumptions and artifact status.
7. **Mandatory Script Review:** Before any topic TTS/render, run `uv run math-books review <topic>` and require `ok: true`. See `docs/scenario-review.md` and `content_reviews/<topic>.json`. Both scientific and pedagogical judgments must refer to the current dossier hash. `--force` and cached audio do not bypass this. Never fabricate approval or copy old verdicts onto changed content. Record AI reviewers as AI. The gate checks recorded judgments and exact calculations, not scientific truth automatically.
