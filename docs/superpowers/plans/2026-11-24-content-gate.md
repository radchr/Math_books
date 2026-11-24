# Content Review Gate Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; independent review at completion.

**Goal:** Block topic production until current scientific and pedagogical review passes.
**Architecture:** One content_review module validates JSON dossiers and executes a small allowlist
of exact rational calculations. Topic entry points share its require_content_review function.
**Tech Stack:** Python stdlib, unittest, existing CLI and test framework; no new dependencies.
**Spec:** docs/superpowers/specs/2026-11-24-content-gate-design.md

## Global Constraints

- No new paid API, no automatic approval, no production bypass flag.
- Use `uv run`; preserve existing output files on rejection.
- Work in current checkout with /tmp/math-books-content-gate-before as baseline; no git writes.

## Review Focus

- A complete-looking dossier with wrong calculation must fail despite approved labels.
- Cached TTS, --force and direct renderer must still require approval before any side effect.
- Changes to sources, learning objective or scene visuals invalidate both reviews.
- JSON with wrong types or duplicate IDs gives actionable failure rather than traceback.
- Existing artifact verification must distinguish current editorial approval from technical media health.

## Task 1: Validator and review templates

Files: src/math_books/content_review.py, tests/test_content_review.py, tests/review_fixtures.py.
Interfaces: script_digest(scenes), dossier_digest(dossier), make_review_template(topic, scenes,
scene_file, root), check_content_review(scenes, video_dir_name, root) -> dict,
require_content_review(...) -> dict (raises ValueError when blocked).
- [x] Write tests for approved, missing, pending, rejected, edited and malformed dossiers.
- [x] Run tests and observe failure before implementation.
- [x] Validate source/claim coverage, teaching fields, criteria and exact math checks; no eval/subprocess.
- [x] Run focused tests; expect all passing.

## Task 2: Enforce and expose the gate

Files: cli.py, tts_engine.py, video_builder.py, tests/test_content_review.py, tests/test_reliability.py.
- [x] Test unapproved TTS (cache/force), build skip-render, direct render and CLI exit before side effects.
- [x] Observe failures, wire shared gate into each boundary and add review / --init commands.
- [x] Give existing test fixtures explicitly approved synthetic dossiers instead of bypassing validation.
- [x] Run full suite; expect passing tests.

## Task 3: Real topic dossiers and documentation

Files: content_reviews/*.json, README.md, GEMINI.md, docs/content-review.md.
- [x] Create pending dossiers for all topics and complete evidence/math/teaching notes for reviewed topics.
- [x] Obtain independent scientific/pedagogical review and record real AI reviewer verdicts explicitly.
- [x] Test actual review statuses; unreviewed topics must stay blocked.
- [x] Run lint/format/unit/lock checks and independent code review; fix important findings.

Progress: docs/superpowers/plans/2026-11-24-content-gate-progress.md.
