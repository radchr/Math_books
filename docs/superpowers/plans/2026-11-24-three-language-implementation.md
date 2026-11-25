# Three-language support for future lessons

**Goal:** future videos support uk/ru/en narration, captions, ASR and review;
existing video scripts and artifacts are not migrated.
**Spec:** ../specs/2026-11-24-three-language-design.md (user scope correction takes precedence).
**Architecture:** shared language validation; localized declarative lessons with a generic
Manim scene; language-aware TTS/QA and isolated lesson outputs. Existing topics retain legacy paths.
**Tech stack:** existing Python/uv, Manim, Gemini/Ukrainian TTS, faster-whisper, unittest.

## Constraints

- Do not modify or regenerate old scripts, review dossiers, WAVs or MP4s.
- Missing translation fails closed; no implicit cross-language fallback or copied approvals.
- Offline tests use synthetic editorial fixtures and explicitly stub only external boundaries.
- Keep separate silent render/WAV/mux flow and frame inspection.
- No automatic commits, publishing, or unrelated refactors.

## Tasks and interfaces

- [x] Language contract: `languages.py` exports `SUPPORTED_LANGUAGES`,
  `validate_language(language: str) -> str`; unsupported codes raise ValueError.
- [x] Spoken QA: `normalize_spoken_text(text, language="ru")` and
  `compare_transcript(expected, transcript, language="ru")`. Write failing tests
  for uk/en exact numbers, negation, units and Unicode; preserve Russian regressions.
- [x] ASR: keyword `language="ru"` on policy, transcription and clip verification;
  manifests derive per-clip language, mixed manifests fail. Language-bound receipts.
  Verify red→green on language forwarding, changed language cache misses and protected text.
- [x] TTS: keyword `language="ru"`, language-aware fingerprints and manifests;
  Ukrainian profile config identity and cache-pinned provider. Preflight cached batch;
  detect mixed voices before publication. External tests use stub providers.
- [x] Future lesson data: `lessons.py` validates `content/lessons/<topic>.json`,
  stable scene IDs and complete uk/ru/en rows. Resolve topic scenes through one helper.
  Test missing translations, unknown languages, IDs, output paths and source hashes.
- [x] Review: bind new lesson dossiers to language/content digest and store under
  `content_reviews/<lang>/<topic>.json`. Do not infer topic from final path component.
  Test pending/changed/wrong-language dossiers fail; legacy fixture behavior stays intact.
- [x] Render/CLI: future topics discovered from lesson data; `--lang` on topic commands.
  `LocalizedLessonScene` uses translated titles/body/formulas before layout; exact manifest
  env path and language passed to subprocess. Fingerprint binds localized content and
  relevant QA words. Test language isolation and stale render rejection.
- [x] End-to-end regression: build synthetic reviewed lesson versions with mocked TTS/ASR
  boundaries; render preview frames separately for each language and inspect them.
- [x] Run full unittest/Ruff/ty/lock checks. Document exact commands, future lesson format,
  real-provider test results or limitations; no claims of real speech QA based only on mocks.

## Review focus

- English speech must not trigger the Russian foreign-word guard.
- Ukrainian і/ї/є/ґ and apostrophes must survive normalization.
- Changed numbers, negation or units must fail even in otherwise similar sentences.
- Partial TTS cache must not mix selected providers/voices; config edits invalidate cache.
- Review and output for one language must not approve or replace another language.
- Test-only synthesized approvals never go in production content_reviews.

## Progress

- Baseline: 119 tests, Ruff, ty and lock passed in prior audit; old media untouched.
- User explicitly restricted work to future videos; removed all old-topic migration tasks.
- Completed: 161 tests, Ruff/format, ty, lock and three skill validators pass.
- Real Edge TTS + actual local Whisper produced passing uk/ru/en smoke receipts.
  Ukrainian defaults to small after base false negatives; strict comparison retained.
- Real three-language Manim renders with verified speech/timings passed stream checks;
  extracted frames inspected. All smoke artifacts remain under /tmp, not old media paths.
- Independent review found direct-API path/renderer, lost-operator, timing-snapshot and
  pinned-retry issues; regression tests reproduce them and fixes pass. Follow-up review
  reports no remaining Important/Critical blockers.
- No old scripts, review dossiers or media regenerated. Test approvals remain temporary.
