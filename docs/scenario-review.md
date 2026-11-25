# Scientific and educational review before production

Every topic needs a current `content_reviews/<topic>.json` dossier **before TTS or rendering**.
The gate runs for CLI TTS, `generate_topic_tts`, `build_video`, direct `render_silent_video`, and
topic-level final verification. Final verification reports editorial rejection before probing media.
`--force`, cached audio and `--skip-render` do not bypass it. Raw HTTP synthesis and generic
`verify_video` are low-level primitives, not approved topic-production entry points.

## What runs automatically

- Exact identity of the current narration, ordering and scene IDs; registered TTS cannot submit an old script.
- Current scene, mathematical example helper and shared visual-helper checksums.
- A learning objective for the project's 12-year-old learner, prerequisites, assumptions, limitations,
  a challenge, and a description of what understanding the challenge should reveal.
- Every scene has a teaching role and claim records with quotes actually present in that scene's narration.
- Empirical claims reference primary sources with a title, HTTP(S) link and page/table/section locator.
- Mathematical claims reference a supported exact check or supply an explicit proof for the reviewer.
- Both scientific and pedagogical reviewers approved the same complete dossier; every required
  criterion has a positive decision and substantive rationale. Open editorial issues block production.
- Strict JSON decoding rejects conflicting/duplicate keys, nonfinite numbers and malformed structures.

Supported arithmetic checks use exact fractions, never `eval`:

```json
{"id": "chain", "kind": "independent_chain", "direct_probability": "3/10", "step_probabilities": ["7/10", "1/2", "7/10"], "expected_chain": "49/200", "expected_comparison": ">"}
```

`independent_chain` checks a nonempty product (up to 100 independent steps)
and compares the direct probability with the exact product. It does not establish
independence or validate the empirical input probabilities.

```json
{"id": "three_points", "kind": "expected_points", "probability": "0.35", "points": 3, "expected": "1.05"}
```

```json
{"id": "coin", "kind": "fair_coin_followups", "expected_sequence_mean": "5/12", "expected_pooled": "1/2"}
```

```json
{"id": "two_shots", "kind": "independent_attempts", "probability": "7/10", "attempts": 2, "expected_at_least_one": "91/100"}
```

`independent_attempts` computes `1 - (1-p)^n` for 1–100 independent attempts with fixed `p`.
The input probability and independence are model assumptions requiring editorial review, not facts
established by evaluating the formula.

The coin check enumerates the actual three-flip example data used by the scene. `expected_points`
checks multiplication for a supplied probability; it does not establish that an empirical probability
is correct or that flips are independent. A conditional-independence argument belongs in `proof`.
Numeric inputs are integers or quoted decimal/fraction strings; boolean/float coercion is rejected.

## What requires substantive review

The validator does **not** infer scientific truth from a source link, check web availability, judge
whether a paper supports a claim, prove arbitrary mathematics, or judge age appropriateness itself.
Those are the recorded reviewers' responsibilities. A dossier is an auditable judgment record,
not a cryptographic identity certificate. Editors with filesystem access can change it.
AI and human reviewers are explicitly distinguished; an AI review is not human expert certification.

Scientific criteria:

- `evidence_matches_claims`: read the cited primary source and match the precise claim and locator.
- `calculations_correct`: verify numbers, units, formulas, conditional probabilities and any proofs.
- `assumptions_and_limits`: check that model assumptions and exclusions are communicated in the lesson.
- `no_overclaim`: distinguish expectation from guarantee and toy models from empirical conclusions.

Pedagogical criteria:

- `age_and_prerequisites`: check the actual wording against a 12-year-old's stated prerequisites.
- `objective_alignment`: each scene should serve the stated learning objective.
- `explanation_clarity`: work through the difficult step, rather than presenting an unexplained answer.
- `challenge_checks_understanding`: the challenge has a meaningful, answerable check of the objective.

## Workflow

1. Write the narration and visual scene. For a newly registered topic, run
   `uv run math-books review <topic> --init`. This creates only a pending template and never overwrites one.
2. Complete `pedagogy`, `sources`, `math_checks`, and `scene_reviews`. Use precise narrative excerpts
   in each `script_quote`, not an entire scene containing several claims. Record unresolved issues.
3. Run `uv run math-books review <topic>`. Fix missing evidence, failed calculations and schema errors.
   The report prints `dossier_sha256` even when judgments are pending.
4. Have a reviewer actually examine the text, visuals, sources and calculations. Record their identity,
   `reviewer_type` (`human` or `ai`), ISO review date, `verdict` (`approved` or `changes_required`),
   that dossier hash and each criterion's `{ "passed": true/false, "rationale": "..." }`.
   Scientific and pedagogical judgments are separate; one reviewer may explicitly assess both.
   Do not set `approved` merely to make the command pass.
5. Run `review` again. Only `ok: true` allows `tts` and `build`. `review all` exits 1 if any topic is blocked.
   A successful `--init` exits 0 for file creation but still reports `status: pending, ok: false`.
6. After any narration, scene, helper, evidence or teaching-design change, repeat review. Archive the old
   dossier in `content_reviews/history/` before replacing it. Refresh its source hashes using
   `make_review_template` from the current source; preserve useful evidence fields, but reset review records
   to pending. Recompute the dossier hash **after** finishing edits; never transplant an old approval hash.
7. Generate and inspect audio, then build and verify the final video. Source approval does not replace
   listening for pronunciation, checking pacing or visually inspecting the actual rendered frames.

## Current state

- `buzzer`: approved scientific/pedagogical source review, verified local ASR audio QA, and verified clean-slate production export in `videos/video_buzzer/buzzer_basketball.mp4`.
- `free_throws`: independently approved AI scientific/pedagogical source review; earlier prototype export archived in `test_videos/video_free_throws/free_throws.mp4`; see [production record](free-throws-video.md).
- `hothand`: independent AI scientific and pedagogical approval of the corrected lesson source (`content_reviews/hothand.json`); prototype export archived in `test_videos/video_hothand/`.
- `moneybart`: approved scientific and pedagogical dossier (`content_reviews/moneybart.json`); prototype export archived in `test_videos/video_moneybart/`.
- `basketball`, `ahrens`, `simpson`: pending dossiers, production blocked; legacy prototype videos archived in `test_videos/`.
- Run `uv run math-books list` to see the live unified status (`review:<state> | audio:<state> | video:<state>`) for every registered topic.
