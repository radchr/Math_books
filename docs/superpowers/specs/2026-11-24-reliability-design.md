# Reliable educational video and digitization pipeline

The user authorized improvements at the implementer's discretion after the critical review.
Keep Python, Manim, ffmpeg, the existing CLI, Russian narration and five-scene format.

## Approach

Improve the current modules rather than replace the pipeline or add a framework.
A rewrite would discard working scenes; documentation-only changes would leave reproducible defects.
Work in place: this repository has no HEAD and all its existing files are untracked, so a
worktree cannot preserve the working baseline. A read-only reference copy lives in /tmp/math-books-before.

## Requirements

- TTS cache requires matching text, voice, prompt revision and model policy; legacy WAV files are untrusted.
  Generate each WAV atomically; retain the actual model and portable relative WAV paths in manifests.
- Silence detection errors and long silence fail verification. Check positive stream durations and 30 fps.
- Reject manifests inconsistent with current scripts or actual WAV durations before rendering.
  Reusing a silent render requires an unchanged render fingerprint (source and audio timing).
  Verify a temporary final video before replacing a previous output.
- Measure scene elapsed time instead of trusting handwritten timing totals; reject overruns.
- Map MinerU page indices to stable source page numbers, independently of requested subsets.
  Missing HTML pages, source images or page mappings must fail explicitly before output is published.
- Explain the hot-hand example as bias in averaging per-sequence estimates, not a changed coin probability.
  Remove the universal basketball bonus. Explain expected points without guaranteed victory.
- Add regression and real ffmpeg integration tests, content assumptions/source notes and usage documentation.
- Rebuild changed videos if the existing API and local render tools allow it; report any external blocker.

No new runtime dependency, publication, remote repository operation or unrelated UI redesign.
