---
name: stem-basketball-video
description: >-
  End-to-end pipeline for creating engaging 9:16 vertical STEM and STEM-basketball educational
  videos in Ukrainian, Russian, or English (with Gemini/Ukrainian TTS voiceover or music_only
  captions mode). Use this skill whenever the user asks to create a new math, physics, chemistry,
  biology, geometry, statistics, or basketball video, adapt a book problem into a video, or build
  a Manim short from the scenario bank.
---

# STEM & STEM-Basketball Video Production Skill

## Declarative Modular Lessons (Preferred for All New Videos)

For all new videos (general STEM — math, physics, chemistry, biology — or STEM-basketball, in `uk`, `ru`, or `en`), use the **scenario bank + declarative lesson + modular `visual_blocks`** workflow ([multilingual guide](../../../docs/three-language-videos.md)):

1. **Scenario Bank (`content/bank/<id>.json`):**
   - Store the idea, domain, tags, sources, pedagogy, and `lesson_draft` in `content/bank/<id>.json`.
   - Promote it to a declarative lesson: `uv run math-books bank promote <id>` → writes `content/lessons/<topic>.json` (with complete `uk/ru/en` translations).
   - Browse/search existing ideas with `uv run math-books bank list` / `search`.
2. **Modular Visual Blocks & Themes (`src/math_books/visual_blocks/`):**
   - Compose scenes from reusable blocks: `text_card`, `hook_choice`, `compare_bars`, `step_chain`, `challenge_card`, `image_stage` (for SVG/PNG diagrams in `assets/diagrams/`), and domain packs like `packs/basketball/{half_court_diagram,scoreboard_duel}`.
   - Pick a named theme: `neutral_dark`, `science_lab`, or `basketball_dark`.
3. **Choose `audio_mode`:**
   - **`"voiceover"` (default, 55–70s):** Full narration in `uk`/`ru`/`en`, Gemini TTS primary (auto-fallback to `uk` chain for `--lang uk` if Gemini is unavailable), automatic local `faster-whisper` ASR QA (`small` for `uk`, `base` for `ru`/`en`), and word-level `cues`.
   - **`"music_only"` (20–45s):** No TTS/ASR. Uses a reusable track from `assets/music/` (`music_track`), explicit per-scene `duration_s`, timed `cues`, and concise on-screen captions/diagrams. Manage tracks via `uv run math-books music list | generate --backend procedural|lyria|musicgen|ace_step | import`.
4. **Mandatory Editorial Review Gate (Both `voiceover` and `music_only`!):**
   - Initialize & approve `content_reviews/<lang>/<topic>.json` via `uv run math-books review <topic> --lang <lang> --init` and `anti-slop-review` on the actual localized text (for `music_only`, `script_quote` matches synthesized on-screen captions).
   - Require `ok: true` before TTS or build. Never copy approvals across languages.
5. **Synthesize (voiceover only), Build & Verify:**
   - Voiceover only: `uv run math-books tts <topic> --lang <lang> --trim-edges` and `uv run math-books verify-audio <topic> --lang <lang>`.
   - Build & verify (both modes): `uv run math-books build <topic> --lang <lang>` and `uv run math-books verify <topic> --lang <lang> --frames`.
   - Inspect all extracted PNGs in `videos/video_<topic>/<lang>/preview_frames/` with `read_file`.

The legacy custom Python-scene recipe below remains available only when a video needs bespoke Manim animations not covered by `visual_blocks`; do not regenerate the seven legacy Russian topics unless explicitly requested.

---

## Legacy Custom Python-Scene Recipe (Russian / Bespoke Manim)

Create 55–70 second vertical (`1080×1920`, `30 fps`) popular-science videos connecting **basketball** (NBA, streetball, court tactics, shooting physics, analytics) with **mathematics** (geometry, algebra, probability, game theory, statistics) for a 12-year-old viewer.

---

## Audience & Storytelling Rules

- **Target Viewer:** 12-year-old boy who loves basketball and dislikes dry textbook math.
- **No Textbook Tone:** Never start with *"Сегодня мы изучим..."*. Open with a strong hook, myth-busting question, NBA star, or counterintuitive paradox in the first 3–5 seconds.
- **Scientific & Pedagogical Rigor:**
  - Every video must have **one clear learning objective**, explicit model assumptions (e.g., independent shots, fixed probability), and honest limitations (distinguish mathematical expectation/probability from a guaranteed single-game outcome; do not claim certainty from a 2–10 shot sample).
  - **Concreteness Fading (Bruner / CRA) & P-O-E:** Start with a concrete court situation or prediction question (*Predict*), show the visual mechanism (*Observe*), reveal the math formula *only after* the viewer already sees the intuition (*Explain*), and end with a 10-second transfer challenge (*Mission*).
  - **Cognitive Load & Multimedia Design (Sweller / Mayer):**
    - Keep at most **3–4 active visual elements** on screen at once; avoid cluttering the 9:16 frame.
    - **Spatial Contiguity:** Place labels, percentages, and vectors directly next to the court/ball/bar they describe rather than in a distant legend.
    - **Signaling:** Highlight only the currently discussed variable or bar in accent color (`ACCENT_ORANGE`, `ACCENT_CYAN`, `ACCENT_GOLD`, `ACCENT_MINT`).
- **5-Scene Structure (55–70s total, ~130–170 Russian words total):**
  1. `01_hook` (~8–14s): Surprising question, myth, or pop-culture/NBA hook.
  2. `02_setup` (~12–15s): Concrete basketball scenario and explicit model assumptions with simple, exact numbers.
  3. `03_twist` (~11–16s): The counterintuitive math/physics reveal or complement/expectation calculation.
  4. `04_proof` (~12–16s): Visual explanation (formula, 10×10 model grid, tree, court diagram, chart, or chain) + model boundaries.
  5. `05_challenge` (~9–15s): Transfer challenge or real-court experiment (include a brief pause before revealing an answer if applicable).

---

## Files to Create / Update for a New `<topic>`

1. `src/math_books/generate_<topic>_tts.py` — defines `SCENES` (5 dicts with `id` and `text`) and calls `generate_topic_tts(SCENES, "videos/video_<topic>")`.
2. `src/math_books/<topic>_scene.py` — calls `configure_vertical_9_16()` and defines `<SceneClass>(VerticalShortScene)`.
3. Register a `VideoTopic` entry in `VIDEO_TOPICS` inside [topics.py](../../../src/math_books/topics.py) with `video_dir="videos/video_<topic>"`.
4. `content_reviews/<topic>.json` — mandatory scientific and pedagogical review dossier (created via `uv run math-books review <topic> --init`).

> [!IMPORTANT]
> All new production outputs are generated from a clean slate under `videos/video_<topic>/`. Earlier prototype exports are archived as test artifacts under `test_videos/video_<topic>/`.

---

## Step 1: Write Stress-Safe Russian Script & Visual Scene

1. **Stress & Pronunciation Rules (`generate_<topic>_tts.py`):**
   - **Separate meaning from notation:** Screen `MathTex` carries the exact formula; TTS narration carries the human idea. Never read raw symbols mechanically (*«пе дорівнює...»*); explain what the quantity means in natural speech.
   - Write **all numbers and percentages in words** (`одиннадцать`, `двадцати одного`, `тридцать пять процентов`, or in Ukrainian: `тридцять п'ять відсотків`, `половина` instead of robotic decimals where exact).
   - In Russian scripts, always use **`ё`** (`идёт`, `нырнёт`, `трёхочковый`, `счёт`, `всё`, `мёртвой`).
   - Keep sentences short enough to speak comfortably in one breath. Never pass Markdown, LaTeX, URLs, abbreviations (`NBA` → `Эн-Би-Эй` / `НБА` or `лига`), or stage directions (`[pause]`) inside the raw TTS `text` field.
2. **Build the Vertical 9:16 Manim Scene (`<topic>_scene.py`):**
   - **Canvas & Reusable UI ([video_ui.py](../../../src/math_books/video_ui.py)):**
     - Call `configure_vertical_9_16()` and subclass `VerticalShortScene` (`1080×1920`, `frame_width=9.0`, `frame_height=16.0`, `30 fps`, `#0D1B2A`).
     - Load audio durations via `durations = self._load_durations("videos/video_<topic>")` (or `"video_<topic>"`).
     - Reuse palette & components: `FONT`, `ACCENT_ORANGE`, `ACCENT_CYAN`, `ACCENT_GOLD`, `ACCENT_MINT`, `CARD_BG`, `make_badge`, `make_subtitle`, `make_caption`, `make_basketball`, `make_half_court`, `make_scoreboard`, `make_stat_card`.
   - **9:16 Safe Layout Grid (`x ∈ [-4.5, +4.5]`, `y ∈ [-8.0, +8.0]`):**
     - `y = +6.5`: Top pill badge (`make_badge`).
     - `y = +5.2`: Section subtitle (`make_subtitle`).
     - `y ∈ [-3.2, +4.2]`: Main visual stage (court, diagrams, cards, formulas).
     - `y = -4.6`: Bottom caption card (`make_caption`).
     - `y < -6.0`: Keep clear (Shorts/TikTok UI safe zone).
     - **Horizontal safety:** Keep all elements within `width ≤ 7.6` (`x ∈ [-3.8, +3.8]`). Constrain wide text with `if mob.width > 7.6: mob.scale_to_fit_width(7.6)`.
   - **Data-Driven Math & Visuals (Single Source of Truth):**
     - Derive all displayed formulas, percentages, chart heights, and verdict labels from one pure Python model function using exact `fractions.Fraction` arithmetic (see `build_buzzer_visual_spec()` in [buzzer_scene.py](../../../src/math_books/buzzer_scene.py)), rather than hardcoding visual numbers separately from math helpers.
     - Add unit tests and `hypothesis` property-based tests in `tests/` verifying bounds, equality handling, and consistency between the model and rendered visual labels.
   - **Critical Manim & Sync Invariants:**
     - Prefer `TransformMatchingTex` for smooth formula substitutions and `ValueTracker` + `always_redraw` for continuous ball/chart animations over abrupt static swaps.
     - **NEVER use `self.add_sound()`** inside `Scene` — Manim's partial-movie caching drops audio on subsequent scenes. Always render silent video and mux in Step 4.
     - **NEVER put Cyrillic inside `MathTex()`** — default `latex` fails on Cyrillic. Use `Text(..., font=FONT)` for Russian labels and `MathTex()` strictly for numbers/Latin/Greek symbols.
     - **Authoritative Timing, Word-Level Bookmarks & Transitions:**
       - Run each scene via `self.run_segment(self.scene_fn, durations[key])`.
       - For intra-scene reveals (e.g., revealing a challenge answer right when the narrator says `"Ответ"` or `"Да"`), query the exact spoken word timestamp from the cached local ASR receipt via `self.word_timestamp(scene_id, "ответ", fallback=duration * 0.7, after_s=elapsed + 0.5)`.
       - Inside each scene method, call `self._pad(duration)` before the exit transition (`_pad` automatically verifies `self.check_frame_bounds()` so no Mobject overflows `|x| <= 4.35` or `y in [-6.15, +7.45]`, and measures actual `self.renderer.time - self._segment_start`, raising `ValueError` if animations overrun narration).
       - End scenes 1–4 with **`self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)`** (use `Group`, never `VGroup`, to safely handle all Mobject types; `0.4s` matches the `400 ms` inter-scene audio gap).
       - End scene 5 with **`self.wait(0.3)`** (matches the `300 ms` tail silence).

---

## Step 2: Mandatory Scientific & Pedagogical Review Gate

Before generating any TTS audio or rendering Manim video, the topic must pass the offline editorial gate ([docs/scenario-review.md](../../../docs/scenario-review.md)):

1. **Initialize Dossier Template (never overwrites existing files):**
   ```bash
   uv run math-books review <topic> --init
   ```
2. **Complete `content_reviews/<topic>.json`:**
   - Fill in `pedagogy` (`audience_age: 12`, `learning_objective`, `prerequisites`, `assumptions`, `limitations`, `challenge`, `expected_learning`).
   - Add `sources` (`primary` or `textbook` with valid HTTP(S) `url` and `locator`) and deterministic `math_checks` (`independent_attempts`, `expected_points`, `fair_coin_followups`, `independent_chain`) or explicit `proof` strings.
   - Map every scene in `scene_reviews` with exact `script_quote` substrings from `SCENES`.
3. **Record Substantive Review & Verify Gate:**
   - Run `uv run math-books review <topic>` to inspect any schema/calculation issues and obtain `dossier_sha256`.
   - Record actual `scientific` and `pedagogical` review judgments (`reviewer`, `reviewer_type: "ai"` or `"human"`, `reviewed_at`, `verdict: "approved"`, `dossier_sha256`, and per-criterion `passed` + `rationale`).
   - Re-run and require `ok: true`:
     ```bash
     uv run math-books review <topic>
     ```
   - If you later edit `SCENES`, `<topic>_scene.py`, `lesson_math.py`, or `video_ui.py`, archive the old dossier in `content_reviews/history/` and re-review with updated hashes.

---

## Step 3: Generate TTS Audio & Run Local ASR Voiceover QA

1. **Generate Audio via CLI (with optional edge silence trimming):**
   ```bash
   # Default for all languages (uk/ru/en): Gemini TTS primary; for --lang uk auto-falls back to uk chain if Gemini is unavailable
   uv run math-books tts <topic> --lang uk --trim-edges

   # Force Ukrainian fallback chain explicitly (StyleTTS2 -> optional Piper -> Edge TTS)
   uv run math-books tts <topic> --lang uk --provider uk --uk-profile tyshyn --trim-edges
   ```
   - **Gemini (`--provider gemini`, primary default for `uk`/`ru`/`en`):** Uses [tts_engine.py](../../../src/math_books/tts_engine.py): sends only raw narration text (`PROMPT_REVISION = 2`), passes `GEMINI_API_KEY` via `x-goog-api-key` header (redacted from errors), rotates `gemini-3.8-flash-tts` (clips 1–3) → `gemini-2.5-flash-preview-tts` / `gemini-3.8-flash-lite-tts` (clips 4–5), and retries transient `httpx.HTTPError` / rate limits while failing fast on 400/401/403. For `--lang uk` without an explicit `--provider`, unavailability falls back automatically to the Ukrainian chain.
   - **Ukrainian Fallback (`--lang uk --provider uk`):** Uses [uk_tts_providers.py](../../../src/math_books/uk_tts_providers.py) and [voice_profiles.toml](../../../src/math_books/voice_profiles.toml) (`StyleTTS2` → optional local `Piper` → `Edge TTS`), pins the first working provider for the entire batch (never mixing voices mid-video), and normalizes every clip to 24 kHz mono 16-bit PCM WAV.
   - Writes immutable WAV files under `videos/video_<topic>/audio/clips/<id>-<fp>-<sha>.wav`, per-scene `.cache.json`, and `videos/video_<topic>/audio/manifest.json`.
   - **Automatic Local ASR Gate (`voiceover_qa.py`):** Every generated (or cached) clip is transcribed locally with the selected language/model and compared against the script. Unexpected added speech, repeated takes or altered numbers/negation/math terms block publication. English itself is valid for `en`. A retry must preserve the pinned batch identity; ASR unavailability must not trigger paid synthesis retries.
2. **Explicit Audio Verification & Listening QC:**
   ```bash
   uv run math-books verify-audio <topic>
   ```
   - Confirm `ok: true` and inspect `videos/video_<topic>/audio/qa/*.json` receipts.
   - **Never edit immutable files in `audio/clips/` in place** (doing so breaks `wav_sha256` provenance and fails `build`/`verify`).
   - Listen to the clips referenced in `manifest.json` to check Russian word stress and pacing, which ASR cannot certify.

---

## Step 4: Build Video (Render + Concat + Mux + Verify)

```bash
uv run math-books build <topic>
```
This validates editorial approval, audio provenance, and ASR QA receipts; renders the silent Manim video (writing `.render.json`); concatenates the 5 `.wav` clips losslessly via stdlib `wave` (`400 ms` gaps + `300 ms` tail); muxes into `videos/video_<topic>/<output>.mp4` via `ffmpeg` (`-movflags +faststart`); verifies streams; and writes `<output>.build.json` atomically.

> **Fast audio-only rebuild:** Reuse an existing silent render only when scene code, shared UI, and exact audio durations are unchanged: `uv run math-books build <topic> --skip-render`.

---

## Step 5: Final Verification & Code Quality (Mandatory)

1. **Full Provenance, Stream, Sync & Preview Frames:**
   ```bash
   uv run math-books verify <topic> --frames
   ```
   Confirm `width=1080`, `height=1920`, `fps=30.0`, `duration_delta < 1.0`, empty `long_silences_s`, valid `.build.json` and `editorial.ok: true`, and overall `ok: true`.
2. **Visual Frame Inspection:**
   - Inspect all 5 extracted PNGs in `videos/video_<topic>/preview_frames/` with `read_file` to verify zero text clipping, zero overlapping labels, and balanced vertical layout.
3. **Unified Readiness & Full CI Quality Gate (`just ci`):**
   ```bash
   uv run math-books list
   uv run ruff format --check src tests && uv run ruff check src tests && uv run ty check && uv run python -m unittest discover -s tests -v && uv lock --check
   ```
   Confirm `math-books list` shows `(review:approved | audio:unverified | video:unverified)` (fast read-only inventory never certifies media — `verify-audio` and `verify --frames` above are the authoritative proof) and all lint, formatting, `ty` type checks, and `unittest`/`hypothesis` tests pass.
