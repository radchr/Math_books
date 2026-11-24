# Free throws: production record

Topic key: `free_throws`. Target: a Russian five-scene short for a 12-year-old learner.

Learning objective: use the complement rule to calculate the probability of at least one hit in
two independent, constant-probability attempts. The worked model uses `p=0.7`, yielding
`1−0.3²=0.91`. The four outcome weights are 49%, 21%, 21%, 9%. A 10×10 model grid represents
exact weights; it does not predict the realized outcome counts of any 100 attempts.
The challenge changes the hypothetical hit probability to 0.8 and yields 96%.

Primary textbook references:

- [OpenStax 3.2: independence and complement events](https://openstax.org/books/introductory-statistics-2e/pages/3-2-independent-and-mutually-exclusive-events).
- [OpenStax 3.3: multiplication and addition rules](https://openstax.org/books/introductory-statistics-2e/pages/3-3-two-basic-rules-of-probability).

The actual source, assumptions, claims and reviewer verdicts are in
`content_reviews/free_throws.json`; that versioned record controls permission to produce the topic.

```bash
uv run math-books review free_throws
uv run math-books tts free_throws --trim-edges
uv run math-books build free_throws
uv run math-books verify free_throws --frames
```

Expected output: `video_free_throws/free_throws.mp4`.

## Verified production result — 2026-11-24

- Output: `video_free_throws/free_throws.mp4`; 1080×1920, 30 fps.
- Video stream 69.53 s; audio stream 69.62 s; delta 0.09 s; no detected long silences.
- Final source dossier approved independently by an AI scientific/pedagogical reviewer:
  `3a4dd10c734897c98192018937d1d1ef33b60ba78ddb800b0e964b78addd077b`.
- The updated project `.env` key was present without an inherited override; model-list access
  returned HTTP 200 and all five actual TTS generations succeeded without HTTP 429. This tests
  those requests; it does not measure the account's remaining daily quota.
- Clips 01 and 03 contained spoken English synthesis instructions before the Russian take.
  Local faster-whisper base ASR confirmed this. New immutable clips retain the complete Russian
  portions; the original files remain. Clip 05 had 450 ms removed from an internal silent interval,
  preserving all words and a thinking pause. Per-clip edit provenance is in `audio/manifest.json`.
- Local ASR of all five cleaned clips found no leaked English prompt phrases or repeated takes.
  Detailed transcripts and word timestamps are in `audio/qa-transcript-original.json` and
  `audio/qa-transcript-clean.json`. ASR is not human pronunciation certification.
- The challenge's spoken answer begins at 11.40 s within its clip; its visual reveal starts
  at 11.265 s. The question and hint precede the solution.
- Additional cloud audio-QA requests hit a discontinued older-model response (404), then temporary
  high-demand responses (503), so local ASR was used. TTS itself succeeded with the updated key.
- One Manim transition initially rejected a nonvector Mobject inside VGroup. Reproduced by
  `test_scene_transition_handles_nonvector_mobjects`, fixed using Group, then reviewed with a new
  dossier hash before rendering. Original approval retained in the history directory.
- Full test suite: 75 passing tests. Ruff lint/format and `uv lock --check` pass.
- Visually inspected all five scene midpoint frames and a sixth frame after the challenge answer
  appears. Text stays within the frame; branch probabilities, 9-cell miss block, 91% result and
  96% answer are legible. Final `math-books verify free_throws --frames` reports media and editorial
  checks both successful.
