# Review hardening implementation plan

**Goal:** execute the user's five-step review plan without rewriting historical
media or manufacturing renewed editorial approvals.

**Architecture:** keep the existing silent-render/mux pipeline. Separate cheap,
read-only inventory from full verification; move common low-level I/O and topic
metadata below TTS/build/QA. Preserve fail-closed provenance and QA invalidation.

**Constraints:** Python through `uv run`; no real TTS calls; no historical media
regeneration; no copying approval onto changed supporting files; existing
untracked buzzer QA receipts are user workspace state and remain untouched.

- [x] Secret transport: header authentication, redacted diagnostics, fake-key
  HTTP/response regressions (new test_secret_transport.py).
- [x] Read-only list: no ASR/media subprocesses/writes, existing-lock busy handling,
  explicit unverified statuses; shared manifest provenance validator.
- [x] Atomic render/event JSON publication: same-directory staging/replace,
  old JSON survives failed publication; correct README/AGENTS examples.
- [x] Trusted legacy timing snapshot with Unicode exact matching; remove unused
  localized method; conservative language-specific protected tokens and tests.
- [x] Extract WAV/locking/errors/topic metadata to remove cross-layer cycles;
  remove unused dependencies; add generic exact probability-chain math check and
  pending buzzer review proposal without touching the approved dossier.
- [x] Full unittest/Ruff/ty/lock, read-only CLI filesystem check, independent review.

**Review focus:** busy readers may not create lock files; missing receipts must
not launch ASR from list; sanitization must cover server-body echoes; semantic
words may not become tolerated typos; abrupt sidecar failure must preserve the
previous parseable JSON. Supporting UI/policy edits intentionally make old
approvals/receipts stale; document recovery order rather than bypassing gates.
