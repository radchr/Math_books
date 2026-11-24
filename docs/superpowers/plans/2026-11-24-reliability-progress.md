# Execution ledger — plan: docs/superpowers/plans/2026-11-24-reliability.md

User delegated design and execution choices; proceeding inline without approval checkpoints.
Baseline: 6 unittest tests passed in the prior audit; current baseline rerun before implementation.
Ruling: work in place and retain /tmp/math-books-before as a review baseline because the repository has no HEAD.
Git commits are deferred: .git is read-only in this workspace and original project files are all untracked.
Pre-flight: Task 1 relative manifests are consumed by Task 3 validation and existing scene duration loader; list shape retained.

Task 1: complete. Cache text/voice/legacy/failed-generation tests observed failing before fixes;
full suite then passed. Final review strengthened publication to immutable clip paths plus atomic
manifest replacement and a per-topic lock. WAV PCM length is checked, not only the header.

Task 2: complete. Five regressions failed before fixes. Page 14 now extracts its illustration alone;
reviewer confirmed identical Markdown and image bytes versus extraction as part of 13–16.
Source-page order is preserved; missing HTML, scans, mapping and invalid bounds raise errors.

Task 3: complete. Silence, detector-failure, frame-rate, invalid-duration and measured-padding
regressions observed failing before fixes. Added full source/audio/final-video provenance,
silent-video checksums, stale-render rejection, legacy refusal and concise CLI errors.
Candidate MP4 verification precedes replacing the final output.

Task 4: source and hot-hand artifact complete; MoneyBART export blocked by external Gemini 429 quota.
No repeated requests after quota failure. Prior MoneyBART audio and video remain intact.
Corrected hot-hand MP4 rebuilt after edge-silence cleanup: 62.97 s video / 63.05 s audio,
1080×1920, 30 fps, delta 0.08 s, no long silence; full verify passed. All five frames inspected.
Full listening/pronunciation review is not claimed.

Final review: independent reviewer review_reliability identified atomic audio publication,
legacy trust, render dependency/checksum, truncated WAV and short all-silent video failures.
Reproductions for publication, WAV and silence failed then passed after fixes. Additional regressions
cover stale dependency data, replaced silent MP4 and untrusted legacy manifests. Fixed MoneyBART
history/per-possession overclaims and the hot-hand formula's units. No review findings deferred.

Final verification: 40/40 unittest tests passed, Ruff check passed, Ruff formatting passed,
uv lock --check passed. Real ffmpeg tone/silence integration test included.
verify all intentionally exits 1 for the four retained legacy/stale exports; hothand passes.

Decisions: work in place because there is no git HEAD; no commit was created in the read-only .git.
Reject legacy narration rather than retroactively invent provenance. Retain old immutable audio
versions, so disk use grows until explicit cleanup. Gemini quota prevents completing MoneyBART export.
