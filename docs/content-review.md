# Educational content review

The mandatory production gate is implemented; follow [the scenario-review workflow](scenario-review.md).
Current executable statuses are in `content_reviews/*.json`. Source judgments and technical export
verification are separate. The notes below also contain historical artifact results.

## Editorial rule

Each short needs one learning objective, explicit model assumptions, a source for empirical
claims, and a challenge that does not promise certainty from a tiny sample. A successful
media verification does not certify the narration's truth. Preview frames do not replace listening.

## Hot hand — revised 2026-11-24

**Objective:** distinguish an equally weighted mean of per-sequence proportions from a pooled proportion.

Fair, independent coin flips; exactly three flips per sequence. Enumerate all eight equally likely
sequences and exclude the two with no observable flip following heads. Six remaining sequences yield
rates `1, 1/2, 0, 0, 1, 0`. Their equally weighted mean is `5/12 ≈ 41.67%`.
Pooling all eligible transitions yields `4/8 = 50%`. A future independent fair-coin flip still
has probability 50% of heads. The bias belongs to the estimator, not to the coin.

The scene uses exact enumerated data from `lesson_math.coin_followup_examples`; its test verifies
both estimators. The three-flip example does not imply any fixed basketball improvement.
Evidence for a basketball hot-hand effect requires data and an appropriate null model; two hits
are not enough to establish it. The corrected script makes no universal bonus claim.

Source: Joshua B. Miller and Adam Sanjurjo, *Surprised by the Hot Hand Fallacy? A Truth in the
Law of Small Numbers*, Econometrica 86(6), 2018, 2019–2047.
[Author paper](https://marketing.wharton.upenn.edu/wp-content/uploads/2018/11/Paper-Joshua-Miller.pdf),
[publication DOI](https://doi.org/10.3982/ECTA14943).

## MoneyBART — revised 2026-11-24

**Objective:** compare expected points per shot, without confusing expectation with a guaranteed score.

Illustrative fixed shooting probabilities, equal numbers of attempts, no turnovers, offensive
rebounds, fouls or free throws: `0.50 × 2 = 1.00` and `0.35 × 3 = 1.05` points per shot.
Over 100 attempts, expected totals are 100 and 105. Realized totals vary; neither strategy guarantees
winning a match. Shot selection depends on player, defence and situation. Ten attempts per location
start an experiment; they do not settle which location is best. Repeat on several days.

The cartoon is a narrative hook, not a source for NBA history or causal claims.
The mathematical comparison follows directly from the expectation of a Bernoulli score.

## Remaining editorial work

- **Approved and verified in production (`videos/video_buzzer/`):** `buzzer` (*Buzzer-Beater Math: 30% direct three vs 24.5% three-step chain*).
- **Approved editorial dossiers ready for clean-slate generation (`videos/video_<topic>/`):** `free_throws`, `hothand`, `moneybart` (their earlier prototype exports are archived under `test_videos/`).
- **Pending editorial dossiers (`status: pending`):** `basketball`, `ahrens`, `simpson`. In particular, the triangles script's idealized reflection and shooting-angle claims should receive a physics/source review (e.g., Fontanella *The Physics of Basketball*, Havelka *STEM in Basketball*) before publication.

Use `uv run math-books list` for a unified per-topic report across `review`, `audio`, `video`, and `archived test` states.

The list is a read-only inventory; `unverified` is presence, not proof of current
media validity. Use explicit `verify-audio` / `verify` for full checks. Changes to
shared UI and QA intentionally invalidate historical evidence; see
[the 2026-11-25 hardening notes](review-hardening.md) before refreshing old artifacts.
