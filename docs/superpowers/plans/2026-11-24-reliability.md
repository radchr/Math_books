# Pipeline Reliability Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, task by task.

**Goal:** Make existing educational outputs accurate and failures visible.
**Architecture:** Extend current modules with cache provenance, explicit page mapping and strict validation.
**Tech Stack:** Python 3.13, unittest, Manim, ffmpeg, Pillow, httpx.
**Spec:** docs/superpowers/specs/2026-11-24-reliability-design.md

## Global Constraints

- Keep Python, Manim, ffmpeg, the existing CLI, Russian narration and five-scene format.
- No new runtime dependency, publication, remote repository operation or unrelated UI redesign.
- Use `uv run` for Python execution.

## Review Focus

- Cached audio after text/voice changes or missing metadata: regenerate without relabelling old audio.
- A failed generation: preserve the previous WAV and manifest.
- A requested page subset: use the original source mapping; reject missing inputs.
- All-silent audio or a failed ffmpeg detector: return failure, not a successful report.
- Reused renders after duration/source edits: reject stale render and preserve previous final output.

## Task 1: Audio provenance

Files: tts_engine.py, video_builder.py, tests/test_reliability.py.
Interface: manifests retain list shape; WAV paths become relative to manifest; per-clip cache JSON stores request fingerprint.
- [x] Write regression tests for unchanged reuse, changed text/voice, unknown legacy files, atomic failure and portable concat.
- [x] Run tests and observe expected failures.
- [x] Implement fingerprinted per-clip metadata, atomic WAV/manifest writes and relative path resolution.
- [x] Run the full unittest suite; expect PASS.

## Task 2: Stable book pages

Files: build_sample_md.py, cli.py, data/mineru_test/res7_json.json, tests/test_reliability.py.
Interface: optional source_page_numbers argument and --source-pages; JSON page_numbers metadata supplies default.
- [x] Test page 14 alone versus 13–16 and missing HTML/JPG/mapping failures.
- [x] Observe failures, implement stable mapping and preflight validation, run full suite.

## Task 3: Verification and timeline

Files: video_builder.py, video_ui.py, cli.py, tests/test_reliability.py.
Interface: verify_video report keeps current shape; stale input validation before build; sidecar render fingerprint.
- [x] Test silence/detector failure, invalid duration/fps, stale manifests/render, atomic output and measured padding.
- [x] Observe failures, implement checks and measured scene boundaries, run full suite.
- [x] Run real ffmpeg checks on synthetic silent and audible MP4s.

## Task 4: Educational accuracy and delivery

Files: generate_hothand_tts.py, hothand_scene.py, generate_moneybart_tts.py, moneybart_scene.py, README.md, docs/content-review.md.
- [x] Verify coin estimator arithmetic by exhaustive enumeration.
- [x] Correct narration and corresponding visual labels; document sources and assumptions.
- [x] Regenerate hot-hand audio/video and inspect five preview frames. MoneyBART generation attempted;
  Gemini HTTP 429 blocks its corrected export. Prior artifacts retained; retry commands documented.
- [x] Run lint, formatting, all tests, lock check and verify all existing videos.
- [x] Request an independent review, address important findings and record final results.

Progress and decisions: docs/superpowers/plans/2026-11-24-reliability-progress.md.
