# Synchronization and audio QA improvements

**Scope:** future multilingual lessons only; do not regenerate old media or copy approvals.
**Approach:** retain silent render + WAV + mux and independent ASR. Add deterministic cue
events, preserve provider timing as advisory evidence, and gate new audio on measurable defects.
No new neural dependencies until a benchmark justifies them; forced alignment/MOS remain optional research.

## Interfaces and tasks

- [x] `audio_quality.analyze_audio(path)` returns deterministic PCM metrics and status
  `pass|fail|needs_review`, issues and warnings; no mutation. Silence and severe clipping fail,
  loudness/edge pauses warn/review with documented thresholds. Distinguish energy from VAD.
- [x] `voiceover_qa.verify_clip(..., quality_check=False)` adds recomputed acoustic evidence
  when enabled; keep legacy behavior by default. Expose ASR probabilities/segment diagnostics.
  New quality-checked text mismatch returns `needs_review` (not proof of TTS failure).
  `ReviewRequiredError` stops TTS retries; infra errors remain distinct.
- [x] `EdgeTTSProvider` requests word boundaries and saves metadata associated with WAV hash;
  preserve it through staging/cache publication. Record trim offset without editing immutable clips.
  Provider timings remain advisory: they cannot approve spoken content or replace ASR evidence.
- [x] `lessons` accepts optional multilingual cues. `cue_timeline.resolve_cues(...)` resolves
  phrase/occurrence/start-or-end to sample/frame positions; missing/ambiguous invalid cues fail.
  No fallback timing for declared cues. Scene reveals target objects at resolved frame positions.
- [x] Freeze event timeline and ASR snapshot once per build; include both in fingerprint,
  renderer inputs and build provenance. Validate event logs against expected target frames.
- [x] Tests first: malformed cues, repeats, numeric words/digits, missing anchors, frame rounding,
  wrong audio, acoustic defects, review-vs-retry, trim metadata, stale caches and provenance.
- [x] Real three-language test render with delayed formula and inspected frames before/after cue;
  full unittest/Ruff/ty/lock and independent final review. No production approvals for smoke fixtures.

## Decisions

- Cues are data outside spoken text. They contain stable ID, target `title|body|formula`,
  multilingual phrase, explicit occurrence (1-based), and anchor `start|end`.
- Word alignment remains ASR based for now. Provider-native boundaries are saved for future A/B
  evaluation; adopting them blindly after MP3 decode/trim would overstate timing accuracy.
- New lessons opt into acoustic checks through their pinned-batch contract. Existing tests and
  legacy synthesis keep their current default semantics; new `needs_review` still blocks production.
- Measured loudness and clipping do not certify naturalness, pronunciation, stress or voice identity.
