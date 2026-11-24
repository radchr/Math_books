# Mandatory scientific and educational script review

User authorized the previously proposed pre-TTS review gate. Keep existing CLI and dependencies.
Implement inline in the current checkout (repository still has no HEAD and read-only .git).

Use deterministic validation plus recorded scientific and pedagogical judgments, rather than
pretending an arithmetic test or an automatic model verdict proves scientific truth. No new paid API.

Each topic has content_reviews/<topic>.json containing the exact script hash, scene file hash,
learning objective, age/prerequisites, assumptions, limitations, challenge and expected learning,
sources with locators, scene-by-scene claim/evidence mappings and declarative arithmetic checks.
Empirical claims require a primary source URL; mathematical claims require a checked calculation or
an explicit proof. A source link's presence does not certify its contents or availability.

Scientific and pedagogical reviewers record identity, human/AI type, date, verdict, rationale for each
criterion and hash of the entire dossier excluding review records. Two approved, complete records
are mandatory. Pending/rejected/missing/stale/malformed reviews block the pipeline. Any script,
scene, claim, source or teaching-metadata edit invalidates approval. AI reviews are explicitly labeled.

`math-books review <topic|all>` returns a structured report and nonzero status on failure.
`math-books review <topic> --init` writes a non-overwriting pending template, never approval.
No --force or --skip-render bypass. Check at CLI TTS, generate_topic_tts (including cache hits),
build_video, render_silent_video and final topic verification. Low-level text-to-speech HTTP and
standalone generic media inspectors remain primitives, not topic production entry points.

Seed pending templates for all five topics, approving only dossiers actually reviewed in this task.
Retain preexisting WAV/MP4 files; no need for TTS quota or video rebuilding to demonstrate the gate.
Test missing/changed/rejected/malformed reviews, wrong arithmetic, unknown references, incomplete
scene coverage, cached/forced generation, direct rendering and skipped rendering before side effects.
