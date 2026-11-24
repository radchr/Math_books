# Mandatory voiceover verification

User requests the previously proposed automatic audio check. Keep local ASR independent of Gemini
availability and enforce it after synthesis and before topic rendering/building. No bypass flag.

Use faster-whisper base on CPU and ffmpeg 16 kHz decoding (the temporary production test exposed
a PyAV decoder incompatibility). Cache model weights under ignored .cache/whisper. Compare Russian
transcripts with narration using number/percent normalization, ё/е handling and morphological
normalization. Missing/extra phrases, repetitions, foreign prompt words and changed numbers or
negation block production. Small noncritical ASR substitutions may be tolerated explicitly and
reported; recognition is a heuristic, not a guarantee of correct stress or pronunciation.

Persist transcripts and reports tied to audio bytes, exact expected text and the verification
policy/model profile. Recompute comparison when consuming a receipt; stale, malformed, failed or
missing receipts cannot masquerade as approved. Cache hits require the same verification.

New TTS requests contain only the spoken script. Increment prompt revision; preserve truthful
legacy revision-1 provenance for existing clips, requiring the new audio check before use.
Generate at most twice per bad clip using the existing model choices. Publish the batch manifest
only after every clip passes, preserving previous audio/MP4s on any failure. Backend failures are
not evidence of bad speech and must fail clearly, rather than spend API calls on retries.

`math-books verify-audio <topic|all>` runs/refreshes missing verification without calling TTS.
`tts`, `build`, direct renderer and topic verification share the gate. Tests mock only external
recognition/synthesis; run the actual local recognizer on the existing free_throws audio and compare
the retained original prompt-leak clips as a negative integration case. No new video or paid API
call is required to verify this feature. Work in place; no HEAD and .git remains read-only.
