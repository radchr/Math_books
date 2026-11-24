# Free Throws Test Video Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with independent editorial/code review.

**Goal:** Deliver a new reviewed test MP4 and verify the updated Gemini key with actual TTS requests.
**Architecture:** Register a new topic and reuse the existing pipeline. Exact two-shot scene data and
an independent declarative complement check keep the numbers independently verifiable.
**Tech Stack:** Python, Manim, Gemini TTS, ffmpeg, unittest.
**Spec:** docs/superpowers/specs/2026-11-24-free-throws-design.md

## Global Constraints

- Russian narration; five scenes; 1080×1920, 30 fps; target 55–70 seconds.
- Never print Gemini credentials; no gate bypass; no shared UI/math-helper edits.
- Existing checkout has no HEAD and read-only .git; work in place without git writes.

## Review Focus

- At least one includes two hits; four outcomes are not equiprobable.
- Independence is an explicit assumption, not an inferred property of real players.
- The 100-cell grid is an exact model representation, not a claim about any 100 trials.
- The challenge changes p to 80%, giving 96%, not a guaranteed score.
- Verify key health through actual synthesis, not a successful unrelated API call.

- [x] Test exact outcome probabilities, grid count and challenge; observe RED before new scene math.
- [x] Implement narration, visuals, registry and exact independent_attempts gate check; verify GREEN.
- [x] Source the probability rules and prepare a pending dossier; obtain actual AI scientific/pedagogical review.
- [x] Generate TTS with updated key, inspect clips, trim edges, render and inspect all five frames.
- [x] Run tests/lint/lock and final topic verification; record measured artifact/API status.
