# Voiceover QA Implementation Plan

> **For agentic workers:** Execute inline with superpowers:executing-plans; request independent final review.

**Goal:** Block video production when narration does not match its script.
**Architecture:** Separate spoken-text normalization/comparison from ASR/report persistence; reuse
existing TTS staging, immutable clips and topic locks. All topic production boundaries consume QA.
**Tech Stack:** Python, faster-whisper, ffmpeg, Russian morphology/number normalization, unittest.
**Spec:** docs/superpowers/specs/2026-11-24-voiceover-qa-design.md

## Global Constraints

- Local ASR, no extra Gemini dependency for verification; no bypass flag.
- Raw script only in new TTS requests; truthful legacy receipts supported under mandatory QA.
- Preserve previous published audio and video on failure; at most two generation attempts per clip.
- Use uv run, keep model caches ignored, no git writes.

## Review Focus

- ASR substitutions must not hide changed numbers, negation or missing scientific qualifiers.
- Cache hits, --force, direct render and --skip-render must all require current QA.
- Flipping a saved report's ok flag or editing WAV/text/policy cannot bypass verification.
- A missing/unavailable recognizer must block clearly and must not cause paid synthesis retries.
- A later failed scene must not publish a partially regenerated batch.

- [ ] Write failing normalization/comparison tests; implement exact numbers and conservative alignment.
- [ ] Write failing report/cache/backend tests; implement local ASR and version-bound receipts.
- [ ] Test enforcement, raw TTS payload and targeted retry; integrate into TTS/build/CLI and existing fixtures.
- [ ] Run real ASR on clean and leaked original clips; request review, fix important findings.
- [ ] Run full tests/lint/lock, document commands and actual limitations, record final validation.
